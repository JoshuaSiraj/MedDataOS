"""The open case: the patient card, the tools an agent may run, and citation checks."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote, unquote, urlparse

import answer
from datactrl.tools import TOOL_DEFINITIONS, dispatch
from state import log, state

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def web_path(relative: str) -> str:
    parts = [quote(part) for part in Path(relative).parts if part not in ("", ".")]
    return "/case/" + "/".join(parts)


def note_span_url(patient_id: str, doc_id: str, start: int, end: int) -> str:
    """Page URL for one highlighted note span."""
    return (
        f"/api/cases/{quote(patient_id, safe='')}/notes/span"
        f"?id={quote(doc_id, safe='')}&start={int(start)}&end={int(end)}"
    )


def path_key(path: object) -> str:
    """Identity of a case path. Spaces and %20, and a missing /case prefix, are the same file."""
    text = str(path or "").strip()

    for _ in range(3):
        decoded = unquote(text)

        if decoded == text:
            break

        text = decoded

    if "://" in text:
        text = urlparse(text).path or text

    text = text.split("?", 1)[0].replace("\\", "/").rstrip("/")

    if text.startswith("/case/"):
        text = text[len("/case/"):]
    elif text.startswith("case/"):
        text = text[len("case/"):]

    return text


# ---------------------------------------------------------------------------
# Patient card
# ---------------------------------------------------------------------------


@dataclass
class Profile:
    """Demographics the agent read out of the files. Empty until that reply arrives."""

    name: str = ""
    age: str = ""
    sex: str = ""
    blood_type: str | None = None
    allergies: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    data_dates: dict[str, str] = field(default_factory=dict)

    _DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

    @classmethod
    def from_agent(cls, data: object) -> Profile:
        """Keep only well-formed fields, so the page never renders unexpected types."""
        if not isinstance(data, dict):
            raise TypeError("the card is not a JSON object")

        return cls(
            name=cls._text(data, "name"),
            age=cls._text(data, "age"),
            sex=cls._text(data, "sex"),
            blood_type=cls._text(data, "blood_type") or None,
            allergies=cls._strings(data, "allergies"),
            conditions=cls._strings(data, "conditions"),
            data_dates=cls._dates(data.get("data_dates")),
        )

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def _text(data: dict, key: str) -> str:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return ""
        return str(value).strip()

    @staticmethod
    def _strings(data: dict, key: str) -> list[str]:
        items = data.get(key)
        items = items if isinstance(items, list) else []
        return [item.strip() for item in items if isinstance(item, str) and item.strip()]

    @staticmethod
    def _dates(value: object) -> dict[str, str]:
        dates = value if isinstance(value, dict) else {}
        return {
            str(folder): date
            for folder, date in dates.items()
            if isinstance(date, str) and Profile._DATE.fullmatch(date)
        }


@dataclass
class Patient:
    """The card the sidebar renders."""

    id: str
    name: str
    age: str = ""
    sex: str = ""
    blood_type: str | None = None
    allergies: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    modalities: list[dict] = field(default_factory=list)
    data_dates: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Open case
# ---------------------------------------------------------------------------


class Case:
    """The folder this server opened, and the tools that read it."""

    _SERVER_ARGS: ClassVar[tuple[str, ...]] = ("root", "case_id")
    _READS: ClassVar[set[str]] = {"describe", "fetch"}
    _MODALITIES: ClassVar[tuple[tuple[str, str], ...]] = (
        ("notes", "Notes"),
        ("structured", "Tables"),
        ("dicom", "DICOM"),
    )

    def __init__(self) -> None:
        self.tools = [self._exposed(tool) for tool in TOOL_DEFINITIONS]
        self.tool_names = [tool["function"]["name"] for tool in self.tools]
        self._takes_root = {
            tool["function"]["name"]
            for tool in TOOL_DEFINITIONS
            if "root" in tool["function"]["parameters"].get("properties", {})
        }

    # -----------------------------------------------------------------------
    # Inventory
    # -----------------------------------------------------------------------

    def files(self) -> list[dict]:
        """Files the agent may cite. Reads the inventory lists discover actually returns."""
        return [
            {
                "id": ref.get("id"),
                "modality": ref.get("modality"),
                "label": ref.get("label"),
                "web_path": web_path(ref.get("path", "")),
            }
            for ref in self._rows()
        ]

    def dicom_preview_paths(self) -> list[str]:
        """Case paths whose citation should show a DICOM preview image."""
        return [path for path, _resource_id in self._dicom_previews()]

    def dicom_preview_id(self, cited_path: str) -> str | None:
        """Resource id for a cited path that can render a preview, or None."""
        for path, resource_id in self._dicom_previews():
            if path == cited_path:
                return resource_id
        return None

    def _dicom_previews(self) -> list[tuple[str, str]]:
        from datactrl.utils.dicom_views import preview_supported

        found = []

        for ref in self._rows():
            if ref.get("modality") != "dicom" or not isinstance(ref.get("id"), str):
                continue

            raw_meta = ref.get("meta")
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            check = {
                "series_kind": ref.get("series_kind") or meta.get("series_kind"),
                "Modality": ref.get("dicom_modality") or meta.get("Modality"),
            }

            if not preview_supported(check):
                continue

            found.append((web_path(ref.get("path", "")), ref["id"]))

        return found

    def _file_by_id(self, resource_id: object) -> dict | None:
        if not isinstance(resource_id, str) or not resource_id:
            return None

        files = self.files()
        exact = next((item for item in files if item.get("id") == resource_id), None)

        if exact is not None:
            return exact

        return next(
            (
                item for item in files
                if isinstance(item.get("id"), str)
                and len(resource_id) >= 8
                and len(item["id"]) >= 8
                and (item["id"].endswith(resource_id) or resource_id.endswith(item["id"]))
            ),
            None,
        )

    def _rows(self) -> list[dict]:
        if state.report is None:
            return []

        rows = state.report.get("resources")

        if not isinstance(rows, list):
            rows = []

            for key in ("notes", "structured", "dicom"):
                found = state.report.get(key) or []

                if isinstance(found, list):
                    rows.extend(found)

        return [ref for ref in rows if isinstance(ref, dict)]

    def patient(self) -> Patient | None:
        """The card. Demographics come from the agent once it has read the files."""
        if state.root is None:
            return None

        info = state.profile
        report = state.report or {}

        return Patient(
            id=state.root.name,
            name=info.get("name") or state.root.name,
            age=info.get("age") or "",
            sex=info.get("sex") or "",
            blood_type=info.get("blood_type"),
            allergies=info.get("allergies") or [],
            conditions=info.get("conditions") or [],
            modalities=[
                {"label": label, "date": None}
                for key, label in self._MODALITIES
                if report.get(key)
            ],
            data_dates=info.get("data_dates") or {},
        )

    # -----------------------------------------------------------------------
    # Tools
    # -----------------------------------------------------------------------

    def run(self, name: str, arguments: dict, session_id: str) -> dict:
        """Run one tool for a question and remember any file it opened."""
        agent_args = {
            key: value for key, value in arguments.items() if key not in self._SERVER_ARGS
        }
        detail = " ".join(
            f"{key}={value}" for key, value in agent_args.items() if value is not None
        )
        args = dict(agent_args)

        if name in self._takes_root:
            args["root"] = str(state.root)

        try:
            result = json.loads(dispatch(name, args))
        except Exception as exc:  # noqa: BLE001 — return the tool failure to the agent
            message = str(exc) or exc.__class__.__name__
            log("agent", f"tool {name} {detail} error: {message}")
            return {"status": "error", "name": name, "message": message}

        payload = {"status": "ok", "name": name, "result": result}

        if name in self._READS:
            token = self._remember(session_id, name, agent_args, result)

            if token:
                payload["cite"] = token

        log("agent", f"tool {name} {detail} ok")
        return payload

    # -----------------------------------------------------------------------
    # Delivered citations
    # -----------------------------------------------------------------------

    def expand_citations(self, text: str, calls: dict[str, dict]) -> str:
        """Fill file, web_path, command, DICOM, and note span links from each cite token."""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text

        citations = parsed.get("citations") if isinstance(parsed, dict) else None

        if not isinstance(citations, list) or not calls:
            return text

        changed = False

        for citation in citations:
            if not isinstance(citation, dict):
                continue

            handle = citation.get("cite")
            call = calls.get(handle) if isinstance(handle, str) else None

            if not isinstance(call, dict):
                continue

            Contract.apply(citation, call)
            changed = True

        if not changed:
            return text

        return json.dumps(parsed)

    # -----------------------------------------------------------------------
    # Calls remembered for the open question
    # -----------------------------------------------------------------------

    def _remember(self, session_id: str, tool: str, agent_args: dict, result: dict) -> str | None:
        """Record this read and return its cite token, or None when it opened no file."""
        if session_id not in state.pending:
            return None

        ref = self._file_by_id(agent_args.get("resource_id"))

        if ref is None and isinstance(result, dict):
            ref = self._file_by_id(result.get("id"))

        if ref is None:
            return None

        opened = state.reads.setdefault(session_id, [])

        if not any(item["web_path"] == ref["web_path"] for item in opened):
            opened.append(ref)

        calls = state.calls.setdefault(session_id, {})
        token = f"c{len(calls) + 1}"
        record = {
            "tool": tool,
            "arguments": {
                key: value for key, value in agent_args.items() if value is not None
            },
            "file": path_key(ref.get("web_path")).rsplit("/", 1)[-1],
            "web_path": ref["web_path"],
            "modality": ref.get("modality") or "",
            "patient_id": state.root.name if state.root is not None else "",
        }
        dicom = self._call_dicom(ref, tool, agent_args, result)

        if dicom:
            record["dicom"] = dicom

        span = self._call_span(ref, tool, agent_args, result)

        if span:
            record["span"] = span

        calls[token] = record
        return token

    def _call_dicom(self, ref: dict, tool: str, args: dict, result: dict) -> dict:
        """Metadata or the one preview slice this call returned."""
        if ref.get("modality") != "dicom":
            return {}

        if tool == "describe":
            metadata = self._dicom_metadata(result.get("summary"))
            return {"metadata": metadata} if metadata else {}

        view = result.get("view")

        if view not in ("metadata", "preview"):
            view = args.get("view")

        if view == "metadata":
            data = result.get("data")
            raw = data.get("metadata") if isinstance(data, dict) else None
            metadata = self._dicom_metadata(raw)
            return {"metadata": metadata} if metadata else {}

        if view == "preview":
            preview = self._dicom_preview(args, result, ref.get("web_path", ""))
            return {"previews": [preview]} if preview else {}

        return {}

    @staticmethod
    def _dicom_metadata(raw: object) -> dict:
        """The metadata object the tool returned, without empty fields."""
        if not isinstance(raw, dict):
            return {}

        return {
            key: value
            for key, value in raw.items()
            if value is not None and value != "" and value != []
        }

    @staticmethod
    def _dicom_preview(args: dict, result: dict, cited_path: str) -> dict:
        raw_data = result.get("data")
        data = raw_data if isinstance(raw_data, dict) else {}
        raw_bounds = result.get("bounds")
        bounds = raw_bounds if isinstance(raw_bounds, dict) else {}
        raw_meta = data.get("meta")
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        preview: dict[str, object] = {}

        if cited_path:
            preview["web_path"] = cited_path

        slice_index = bounds.get("slice_index", args.get("slice_index"))

        if isinstance(slice_index, bool):
            slice_index = None
        elif isinstance(slice_index, float) and slice_index.is_integer():
            slice_index = int(slice_index)
        elif isinstance(slice_index, str) and slice_index.strip().isdigit():
            slice_index = int(slice_index.strip())

        if isinstance(slice_index, int):
            preview["slice_index"] = slice_index

        n_slices = bounds.get("n_slices")

        if isinstance(n_slices, int):
            preview["n_slices"] = n_slices

        window = bounds.get("window") or meta.get("window")

        if isinstance(window, str) and window:
            preview["window"] = window

        if meta.get("overlay") is True or args.get("overlay") in (True, "true", "True", 1):
            preview["overlay"] = True

        roi = args.get("roi")

        if isinstance(roi, str) and roi.strip():
            preview["roi"] = roi.strip()

        return preview

    @staticmethod
    def _call_span(ref: dict, tool: str, args: dict, result: dict) -> dict:
        """The note text a fetch returned, so a citation can be checked against it.

        Offsets on the citation are into this text. ``origin`` is the file offset of
        ``text[0]``: 0 for a text fetch, and the span start for a span fetch.
        """
        if ref.get("modality") != "note" or tool != "fetch":
            return {}

        view = result.get("view") or args.get("view")
        raw_data = result.get("data")
        data = raw_data if isinstance(raw_data, dict) else {}
        raw_text = data.get("text")
        text = raw_text if isinstance(raw_text, str) else ""

        if view not in ("text", "span") or not text.strip():
            return {}

        if view == "text":
            start, end, origin = 0, len(text), 0
        else:
            start_at = Contract.as_int(data.get("start", args.get("start")))
            end_at = Contract.as_int(data.get("end", args.get("end")))

            if start_at is None or end_at is None or end_at <= start_at:
                return {}

            start, end, origin = start_at, end_at, start_at

        span: dict[str, object] = {
            "start": start,
            "end": end,
            "text": text,
            "origin": origin,
        }
        section = data.get("section")

        if isinstance(section, str) and section.strip():
            span["section"] = section.strip()

        meta_raw = ref.get("meta")
        meta = meta_raw if isinstance(meta_raw, dict) else {}
        note_date = meta.get("note_date")

        if isinstance(note_date, str) and note_date.strip():
            span["note_date"] = note_date.strip()

        return span

    # -----------------------------------------------------------------------
    # Tool list shown to the agent
    # -----------------------------------------------------------------------

    @staticmethod
    def _exposed(tool: dict) -> dict:
        """The datactrl tool, without the arguments the server fills in."""
        spec = copy.deepcopy(tool)
        params = spec["function"]["parameters"]

        for key in Case._SERVER_ARGS:
            params.get("properties", {}).pop(key, None)

        params["required"] = [
            key for key in params.get("required", []) if key not in Case._SERVER_ARGS
        ]
        return spec


# ---------------------------------------------------------------------------
# Citation contract
# ---------------------------------------------------------------------------


class Contract:
    """The citation deal: the text shown to the agent, the checks, and the fields the server fills."""

    MAX_QUOTE = 280

    RULE = (
        "After describe or fetch, the reply is one JSON object that matches the answer schema. "
        "Each citation's kind follows from the call its cite token came from: "
        "imaging for a DICOM series, note for a clinical note, table for a table. "
        "Put [cite:token] right after the words that call supports. "
        "A sentence may cite several calls, but never put markers side by side "
        "or group them at the end of the answer. "
        "A marker may not be the whole sentence. "
        "Do not send id, file, or web_path on a cited call; the server fills those in."
    )

    EXAMPLE: ClassVar[dict] = answer.EXAMPLE

    _MARKER = re.compile(r"\[cite:([^\]]+)\]")
    _ADJACENT = re.compile(r"\[cite:[^\]]+\]\s*[,;]?\s*\[cite:[^\]]+\]")

    # -----------------------------------------------------------------------
    # Prompt
    # -----------------------------------------------------------------------

    @classmethod
    def specialist_rule(cls) -> str:
        """The citation rule for a specialist, which may cite a case file it did not fetch."""
        return (
            "The reply may be plain text. "
            f"{cls.RULE} "
            "If you did not call describe or fetch, each citation has kind file, an id, file, "
            "and web_path, and web_path must be a case file. The marker is then [cite:] plus that id."
        )

    # -----------------------------------------------------------------------
    # Checks
    # -----------------------------------------------------------------------

    @staticmethod
    def has_marker(response: str) -> bool:
        return Contract._MARKER.search(response) is not None

    @staticmethod
    def marker_problem(response: str) -> str | None:
        """A marker follows the words it supports, and markers do not sit side by side."""
        if clump := Contract._ADJACENT.search(response):
            return (
                f"The markers {clump.group(0)!r} sit side by side; "
                "put each one right after the words that call supports."
            )

        protected = Contract._MARKER.sub(lambda match: match.group(0).replace(".", "\0"), response)
        sentences = [part.replace("\0", ".").strip() for part in re.split(r"[.!?]+", protected)]

        for sentence in sentences:
            ids = Contract._MARKER.findall(sentence)

            if ids and not Contract._MARKER.sub("", sentence).strip():
                return f"[cite:{ids[0]}] stands alone; put it right after the words it supports."

        return None

    @staticmethod
    def citation_problem(
        citation: object,
        response: str,
        calls: dict[str, dict],
        paths: dict[str, str],
    ) -> str | None:
        """Why this citation can't back the answer, or None."""
        if not isinstance(citation, dict):
            return "a citation is not an object"

        if not isinstance(citation.get("summary"), str):
            return "a citation needs a \"summary\" string"

        handle = citation.get("cite")
        marker = handle if isinstance(handle, str) and handle else citation.get("id")

        if not isinstance(marker, str) or not re.fullmatch(r"\S+", marker):
            return f"citation marker {marker!r} must be a string with no spaces"

        if f"[cite:{marker}]" not in response:
            return f"[cite:{marker}] does not appear in the response"

        call = calls.get(handle) if isinstance(handle, str) else None
        notes = Contract._notes_problem(citation, marker, call if isinstance(call, dict) else None)

        if notes:
            return notes

        if isinstance(handle, str) and handle:
            if handle not in calls:
                return f"citation cite {handle!r} is not a tool result from this question"
            return None

        web = citation.get("web_path")

        if path_key(web) in paths:
            if not isinstance(citation.get("file"), str) or not citation["file"]:
                return f'citation {marker} needs a "file" name'
            return None

        fetched = {path_key(call.get("web_path")) for call in calls.values()}

        if path_key(web) in fetched:
            return (
                f"citation {marker} must use the cite token for that call, "
                f"not web_path {web!r}"
            )

        if calls:
            return f"citation {marker} needs the cite token from the tool result it uses"

        return f"citation {marker} web_path {web!r} is not an opened file"

    @staticmethod
    def _notes_problem(citation: dict, marker: str, call: dict | None = None) -> str | None:
        """Why the quotes or discrepancies on this citation are unusable, or None."""
        evidence = citation.get("evidence", None)
        fetched = Contract._fetched_text(call)

        if evidence is not None and not isinstance(evidence, list):
            return f"citation {marker} evidence must be a list"

        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, dict):
                    return f"citation {marker} evidence item must be an object"

                if fetched is None and Contract._names_offsets(item) and Contract._span_offsets(item) is None:
                    return (
                        f"citation {marker} evidence start and end must be offsets "
                        "with end greater than start"
                    )

                if fetched is not None:
                    slice_problem = Contract._quote_problem(marker, item, fetched, call)

                    if slice_problem:
                        return slice_problem

        if fetched is not None and not evidence:
            return (
                f"citation {marker} must include evidence with a quote copied "
                "from the text that fetch returned"
            )

        conflicts = citation.get("conflicts", None)

        if conflicts is not None and not isinstance(conflicts, list):
            return f"citation {marker} conflicts must be a list"

        if isinstance(conflicts, list):
            for item in conflicts:
                if not isinstance(item, dict):
                    return f"citation {marker} conflict must be an object"

                if not isinstance(item.get("attribute"), str) or not item["attribute"].strip():
                    return f"citation {marker} conflict needs an attribute"

                values = item.get("values")

                if not isinstance(values, list) or not values:
                    return f"citation {marker} conflict needs a values list"

                for value in values:
                    if not isinstance(value, dict) or not isinstance(value.get("value"), str):
                        return f"citation {marker} conflict value needs a value string"

                    if Contract._names_offsets(value) and Contract._span_offsets(value) is None:
                        return (
                            f"citation {marker} conflict start and end must be offsets "
                            "with end greater than start"
                        )

        return None

    @staticmethod
    def _fetched_text(call: dict | None) -> str | None:
        """The note text stored for this call, or None when there is nothing to check."""
        if not isinstance(call, dict):
            return None

        span = call.get("span")

        if not isinstance(span, dict):
            return None

        text = span.get("text")
        return text if isinstance(text, str) and text else None

    @staticmethod
    def _quote_problem(marker: str, item: dict, text: str, call: dict | None) -> str | None:
        """Refuse a quote that is not a passage in the fetched note."""
        quote = item.get("quote")

        if not isinstance(quote, str) or not quote.strip():
            return f"citation {marker} evidence needs a quote copied from the note"

        if len(text) > Contract.MAX_QUOTE and quote.strip() == text.strip():
            return (
                f"citation {marker} quotes the whole note; "
                "copy the passage that supports the claim"
            )

        found = Contract._find_quote(text, quote, Contract._quote_hint(item, call))

        if found is None:
            return (
                f"citation {marker} quote is not in the text that fetch returned; "
                "copy a contiguous passage from that text"
            )

        return None

    @staticmethod
    def _quote_hint(item: dict, call: dict | None) -> int | None:
        """A model offset, shifted into the fetched text, used when a quote occurs twice."""
        hint = Contract.as_int(item.get("start", item.get("char_start")))

        if hint is None or not isinstance(call, dict):
            return hint

        span = call.get("span")
        origin = Contract.as_int(span.get("origin")) if isinstance(span, dict) else None

        if origin:
            return hint - origin

        return hint

    @staticmethod
    def _find_quote(text: str, quote: str, hint: int | None) -> tuple[int, int] | None:
        """Offsets of this passage in the fetched note, or None when it is absent."""
        needle = quote.strip()

        if not needle:
            return None

        starts = []
        cursor = 0

        while True:
            found = text.find(needle, cursor)

            if found < 0:
                break

            starts.append(found)
            cursor = found + 1

        if starts:
            start = starts[0] if hint is None else min(starts, key=lambda item: abs(item - hint))
            return start, start + len(needle)

        return Contract._find_quote_loose(text, needle)

    @staticmethod
    def _find_quote_loose(text: str, needle: str) -> tuple[int, int] | None:
        """Find a passage whose words match, allowing different spacing."""
        flat_chars: list[str] = []
        index_map: list[int] = []
        previous_space = False

        for index, char in enumerate(text):
            if char.isspace():
                if flat_chars and not previous_space:
                    flat_chars.append(" ")
                    index_map.append(index)
                previous_space = True
                continue

            flat_chars.append(char)
            index_map.append(index)
            previous_space = False

        flat_needle = " ".join(needle.split())
        at = "".join(flat_chars).find(flat_needle)

        if at < 0 or not index_map:
            return None

        start = index_map[at]
        end = index_map[at + len(flat_needle) - 1] + 1
        return start, end

    # -----------------------------------------------------------------------
    # Offsets
    # -----------------------------------------------------------------------

    @staticmethod
    def _names_offsets(item: dict) -> bool:
        return any(key in item for key in ("start", "end", "char_start", "char_end"))

    @staticmethod
    def _span_offsets(item: dict) -> tuple[int, int] | None:
        """Character offsets on a quote or conflict value, or None when they are absent or invalid."""
        start = Contract.as_int(item.get("start", item.get("char_start")))
        end = Contract.as_int(item.get("end", item.get("char_end")))

        if start is None and end is None:
            return None

        if start is None or end is None or end <= start or start < 0:
            return None

        return start, end

    @staticmethod
    def as_int(value: object) -> int | None:
        if isinstance(value, bool) or value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float) and value.is_integer():
            return int(value)

        return None

    # -----------------------------------------------------------------------
    # Fields the server fills
    # -----------------------------------------------------------------------

    @staticmethod
    def apply(citation: dict, call: dict) -> None:
        """Fill id, file, web_path, command, DICOM, and note span links from one cite token."""
        citation["id"] = citation.get("cite")
        citation["file"] = call["file"]
        citation["web_path"] = call["web_path"]
        citation["command"] = {"tool": call["tool"], "arguments": call["arguments"]}

        if call.get("dicom"):
            citation["dicom"] = call["dicom"]

        Contract._fill_notes(citation, call)

    @staticmethod
    def _fill_notes(citation: dict, call: dict) -> None:
        """Copy the note label onto each quote and fill span_url from the cited offsets."""
        evidence = citation.get("evidence")
        conflicts = citation.get("conflicts")
        span = call.get("span") if isinstance(call.get("span"), dict) else None
        has_notes = isinstance(evidence, list) or isinstance(conflicts, list)

        if not has_notes:
            return

        arguments = call.get("arguments")
        resource_id = arguments.get("resource_id") if isinstance(arguments, dict) else None
        resource_id = resource_id if isinstance(resource_id, str) else ""
        patient_raw = call.get("patient_id")
        patient_id = patient_raw if isinstance(patient_raw, str) else ""

        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, dict):
                    continue

                if not item.get("label") and call.get("file"):
                    item["label"] = call["file"]

                if not item.get("note_id") and resource_id:
                    item["note_id"] = resource_id

                Contract._place_quote(item, span)
                note_id = item.get("note_id")
                doc_id = note_id if isinstance(note_id, str) else resource_id
                Contract._fill_span_url(item, patient_id, doc_id)

        if isinstance(conflicts, list):
            for conflict in conflicts:
                if not isinstance(conflict, dict):
                    continue

                values = conflict.get("values")

                if not isinstance(values, list):
                    continue

                for value in values:
                    if not isinstance(value, dict):
                        continue

                    note_id = value.get("note_id")
                    doc_id = note_id if isinstance(note_id, str) else resource_id
                    Contract._fill_span_url(value, patient_id, doc_id)

        if call.get("modality") == "note" and not citation.get("agent"):
            citation["agent"] = "clinical_notes"

    @staticmethod
    def _place_quote(item: dict, span: dict | None) -> None:
        """Turn offsets into the fetched text into file offsets, and copy the note label."""
        if not isinstance(span, dict):
            return

        text = span.get("text") if isinstance(span.get("text"), str) else ""
        origin = Contract.as_int(span.get("origin")) or 0
        quote = item.get("quote")
        found = None

        if isinstance(quote, str):
            found = Contract._find_quote(text, quote, Contract._quote_hint(item, {"span": span}))

        if found:
            local_start, local_end = found
            item["quote"] = text[local_start:local_end]
            item["start"] = origin + local_start
            item["end"] = origin + local_end

        if not item.get("note_date") and isinstance(span.get("note_date"), str):
            item["note_date"] = span["note_date"]

        if not item.get("section") and isinstance(span.get("section"), str):
            item["section"] = span["section"]

    @staticmethod
    def _fill_span_url(item: dict, patient_id: str, doc_id: str) -> None:
        """Point a quote at the span route when it names offsets and has no link yet."""
        if item.get("span_url") or not patient_id or not doc_id:
            return

        offsets = Contract._span_offsets(item)

        if offsets is None:
            return

        start, end = offsets
        item["span_url"] = note_span_url(patient_id, doc_id, start, end)


# ---------------------------------------------------------------------------
# One reply
# ---------------------------------------------------------------------------


class Answer:
    """One agent reply, judged against the files opened for its question."""

    _UNSET = object()

    # -----------------------------------------------------------------------
    # Judgment
    # -----------------------------------------------------------------------

    def __init__(
        self,
        text: str,
        opened: list[dict],
        known: list[dict],
        calls: dict[str, dict] | None = None,
    ) -> None:
        self.text = text.strip()
        self.opened = opened
        self.known = known
        self.calls = calls or {}
        self._problem = self._UNSET

    @property
    def problem(self) -> str | None:
        """What is wrong with this reply, in one sentence, or None when it may be shown."""
        if self._problem is self._UNSET:
            found = self._find_problem()
            self._problem = found
            return found

        return self._problem if isinstance(self._problem, str) else None

    def correction(self) -> str:
        """What the agent is told when this reply is refused."""
        if not self.opened and (self.problem or "").startswith("You opened no files"):
            return f"The server refused that answer. {self.problem}"

        text = (
            f"The server refused that answer. {self.problem} "
            "Send only one JSON object, with no sentences before or after it. "
            f"{Contract.RULE} Example: {json.dumps(Contract.EXAMPLE)}"
        )

        if self.calls:
            shown = ", ".join(
                f"{token}={self._command(call)}" for token, call in self.calls.items()
            )
            text += " Tool results: " + shown

        fetched = {path_key(call.get("web_path")) for call in self.calls.values()}
        names = [
            item["web_path"]
            for item in self.opened
            if path_key(item.get("web_path")) not in fetched
        ]

        if names:
            text += " Opened files: " + ", ".join(names)

        return text

    @staticmethod
    def _command(call: dict) -> str:
        raw = call.get("arguments")
        arguments = raw if isinstance(raw, dict) else {}
        detail = " ".join(f"{key}={value}" for key, value in arguments.items())
        return f"{call.get('tool', '')} {detail}".strip()

    def _find_problem(self) -> str | None:
        if not self.opened and "[cite:" not in self.text and '"citations"' not in self.text:
            if self._is_json_object():
                return "You opened no files, so answer the user in plain text, not JSON."
            return None

        try:
            parsed = json.loads(self.text)
        except json.JSONDecodeError:
            if "{" in self.text:
                return "The reply has text outside the JSON object, or the JSON is invalid."
            return "The reply is plain text, but files were opened, so it must be the citation JSON."

        if not isinstance(parsed, dict):
            return "The reply must be a JSON object."

        response = parsed.get("response")
        citations = parsed.get("citations")

        if not isinstance(response, str) or not isinstance(citations, list):
            keys = ", ".join(parsed) or "none"
            return (
                'The JSON needs a "response" string and a "citations" list. '
                f"It has keys: {keys}."
            )

        if not Contract.has_marker(response):
            return "The response has no [cite:id] markers."

        for item in citations:
            if not isinstance(item, dict):
                continue

            handle = item.get("cite")
            call = self.calls.get(handle) if isinstance(handle, str) else None
            shape = answer.shape_problem(item, call)

            if shape:
                return shape

        problems = [
            Contract.citation_problem(item, response, self.calls, self._web_paths())
            for item in citations
        ]

        if not citations or all(problems):
            found = "; ".join(item for item in problems if item) or "the list is empty"
            return f"No citation is usable: {found}."

        return Contract.marker_problem(response)

    def _is_json_object(self) -> bool:
        try:
            return isinstance(json.loads(self.text), dict)
        except json.JSONDecodeError:
            return False

    def _web_paths(self) -> dict[str, str]:
        """Files a citation may name with web_path. A fetched file must use its cite token."""
        fetched = {path_key(call.get("web_path")) for call in self.calls.values()}
        source = self.opened or self.known
        return {
            path_key(item.get("web_path")): item["web_path"]
            for item in source
            if isinstance(item.get("web_path"), str)
            and path_key(item.get("web_path")) not in fetched
        }


case = Case()
