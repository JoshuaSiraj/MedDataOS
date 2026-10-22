"""The open case: the patient card, the tools an agent may run, and citation checks."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from typing import ClassVar
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from datactrl.tools import TOOL_DEFINITIONS, dispatch

from state import log, state


def web_path(relative: str) -> str:
    parts = [quote(part) for part in Path(relative).parts if part not in ("", ".")]
    return "/case/" + "/".join(parts)


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
            raise ValueError("the card is not a JSON object")

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
        except Exception as exc:
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

    def expand_citations(self, text: str, calls: dict[str, dict]) -> str:
        """Fill file, web_path, command, and DICOM from the cite token on each citation."""
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

            citation["id"] = handle
            citation["file"] = call["file"]
            citation["web_path"] = call["web_path"]
            citation["command"] = {"tool": call["tool"], "arguments": call["arguments"]}

            if call.get("dicom"):
                citation["dicom"] = call["dicom"]

            changed = True

        if not changed:
            return text

        return json.dumps(parsed)

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
        }
        dicom = self._call_dicom(ref, tool, agent_args, result)

        if dicom:
            record["dicom"] = dicom

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


class Answer:
    """One agent reply, judged against the files opened for its question."""

    RULE = (
        "After describe or fetch, the reply is one JSON object with a \"response\" string "
        "and a \"citations\" list, like the example. "
        "Put [cite:token] right after the words that call supports. "
        "Several tokens may follow one claim. A marker may not be the whole sentence. "
        "Each citation's cite is that same token from the tool result. "
        "Do not send id, file, or web_path; the server fills those in."
    )

    EXAMPLE: ClassVar[dict] = {
        "response": (
            "The planning CT and the contours show the larynx [cite:c1] [cite:c2]. "
            "Treatment finished on February 13 [cite:c3]."
        ),
        "citations": [
            {"cite": "c1", "summary": "CT slice that supports the first claim."},
            {"cite": "c2", "summary": "RTSTRUCT that supports the same claim."},
            {"cite": "c3", "summary": "Note that supports the second sentence."},
        ],
    }

    _MARKER = re.compile(r"\[cite:([^\]]+)\]")
    _UNSET = object()

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
            f"{self.RULE} Example: {json.dumps(self.EXAMPLE)}"
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

        if not self._MARKER.search(response):
            return "The response has no [cite:id] markers."

        problems = [
            self._citation_problem(item, response, self._web_paths()) for item in citations
        ]

        if not citations or all(problems):
            found = "; ".join(item for item in problems if item) or "the list is empty"
            return f"No citation is usable: {found}."

        return self._marker_problem(response)

    def _is_json_object(self) -> bool:
        try:
            return isinstance(json.loads(self.text), dict)
        except json.JSONDecodeError:
            return False

    def _citation_problem(self, citation: object, response: str, paths: dict[str, str]) -> str | None:
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

        if isinstance(handle, str) and handle:
            if handle not in self.calls:
                return f"citation cite {handle!r} is not a tool result from this question"
            return None

        web = citation.get("web_path")

        if path_key(web) in paths:
            if not isinstance(citation.get("file"), str) or not citation["file"]:
                return f'citation {marker} needs a "file" name'
            return None

        fetched = {path_key(call.get("web_path")) for call in self.calls.values()}

        if path_key(web) in fetched:
            return (
                f"citation {marker} must use the cite token for that call, "
                f"not web_path {web!r}"
            )

        if self.calls:
            return f"citation {marker} needs the cite token from the tool result it uses"

        return f"citation {marker} web_path {web!r} is not an opened file"

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

    def _marker_problem(self, response: str) -> str | None:
        """A marker follows the words it supports and is not the whole sentence."""
        protected = self._MARKER.sub(lambda match: match.group(0).replace(".", "\0"), response)
        sentences = [part.replace("\0", ".").strip() for part in re.split(r"[.!?]+", protected)]

        for sentence in sentences:
            ids = self._MARKER.findall(sentence)

            if ids and not self._MARKER.sub("", sentence).strip():
                return f"[cite:{ids[0]}] stands alone; put it right after the words it supports."

        return None


case = Case()
