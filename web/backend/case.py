"""The open case: the patient card, the tools an agent may run, and citation checks."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from typing import ClassVar
from pathlib import Path
from urllib.parse import quote

from datactrl.tools import TOOL_DEFINITIONS, dispatch

from state import log, state


def web_path(relative: str) -> str:
    parts = [quote(part) for part in Path(relative).parts if part not in ("", ".")]
    return "/case/" + "/".join(parts)


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
        if state.report is None:
            return []

        return [
            {
                "id": ref.get("id"),
                "modality": ref.get("modality"),
                "label": ref.get("label"),
                "web_path": web_path(ref.get("path", "")),
            }
            for ref in state.report.get("resources", [])
        ]

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
        args = {key: value for key, value in arguments.items() if key not in self._SERVER_ARGS}
        detail = " ".join(f"{key}={value}" for key, value in args.items() if value is not None)

        if name in self._takes_root:
            args["root"] = str(state.root)

        try:
            result = json.loads(dispatch(name, args))
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            log("agent", f"tool {name} {detail} error: {message}")
            return {"status": "error", "name": name, "message": message}

        if name in self._READS:
            self._remember(session_id, args.get("resource_id"))

        log("agent", f"tool {name} {detail} ok")
        return {"status": "ok", "name": name, "result": result}

    def _remember(self, session_id: str, resource_id: str | None) -> None:
        if session_id not in state.pending:
            return

        ref = next((item for item in self.files() if item["id"] == resource_id), None)
        opened = state.reads.setdefault(session_id, [])

        if ref and all(item["web_path"] != ref["web_path"] for item in opened):
            opened.append(ref)

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
        "Put each [cite:id] right after the words that file supports. "
        "A sentence may cite several files, but never put markers side by side "
        "or group them at the end of the answer. "
        "Each citation's web_path must be one of the files opened for this question."
    )

    EXAMPLE: ClassVar[dict] = {
        "response": (
            "The planned dose was 51 Gy [cite:1]. "
            "Treatment finished on February 13 [cite:2]."
        ),
        "citations": [
            {
                "id": "1",
                "file": "note.txt",
                "web_path": "/case/note.txt",
                "summary": "Short excerpt that supports the sentence.",
            },
            {
                "id": "2",
                "file": "completion.txt",
                "web_path": "/case/completion.txt",
                "summary": "Short excerpt for the second sentence.",
            },
        ],
    }

    _MARKER = re.compile(r"\[cite:([^\]]+)\]")
    _ADJACENT = re.compile(r"\[cite:[^\]]+\]\s*[,;]?\s*\[cite:[^\]]+\]")
    _UNSET = object()

    def __init__(self, text: str, opened: list[dict], known: list[dict]) -> None:
        self.text = text.strip()
        self.opened = opened
        self.known = known
        self._problem = self._UNSET

    @property
    def problem(self) -> str | None:
        """What is wrong with this reply, in one sentence, or None when it may be shown."""
        if self._problem is self._UNSET:
            self._problem = self._find_problem()
        return self._problem

    def correction(self) -> str:
        """What the agent is told when this reply is refused."""
        if not self.opened and (self.problem or "").startswith("You opened no files"):
            return f"The server refused that answer. {self.problem}"

        text = (
            f"The server refused that answer. {self.problem} "
            "Send only one JSON object, with no sentences before or after it. "
            f"{self.RULE} Example: {json.dumps(self.EXAMPLE)}"
        )

        if self.opened:
            text += " Opened files: " + ", ".join(item["web_path"] for item in self.opened)

        return text

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

        paths = {item["web_path"] for item in (self.opened or self.known)}
        problems = [self._citation_problem(item, response, paths) for item in citations]

        if not citations or all(problems):
            found = "; ".join(item for item in problems if item) or "the list is empty"
            return f"No citation is usable: {found}."

        return self._marker_problem(response)

    def _is_json_object(self) -> bool:
        try:
            return isinstance(json.loads(self.text), dict)
        except json.JSONDecodeError:
            return False

    def _citation_problem(self, citation: object, response: str, paths: set[str]) -> str | None:
        """Why this citation can't back the answer, or None."""
        if not isinstance(citation, dict):
            return "a citation is not an object"

        cite_id = citation.get("id")

        if not isinstance(cite_id, str) or not re.fullmatch(r"\S+", cite_id):
            return f"citation id {cite_id!r} must be a string with no spaces"

        if citation.get("web_path") not in paths:
            return f"citation {cite_id} web_path {citation.get('web_path')!r} is not an opened file"

        if not isinstance(citation.get("file"), str) or not citation["file"]:
            return f'citation {cite_id} needs a "file" name'

        if not isinstance(citation.get("summary"), str):
            return f'citation {cite_id} needs a "summary" string'

        if f"[cite:{cite_id}]" not in response:
            return f"[cite:{cite_id}] does not appear in the response"

        return None

    def _marker_problem(self, response: str) -> str | None:
        """Each marker follows the words it supports: none stand alone or side by side."""
        if clump := self._ADJACENT.search(response):
            return (
                f"The markers {clump.group(0)!r} sit side by side; "
                "put each one right after the words that file supports."
            )

        protected = self._MARKER.sub(lambda match: match.group(0).replace(".", "\0"), response)
        sentences = [part.replace("\0", ".").strip() for part in re.split(r"[.!?]+", protected)]

        for sentence in sentences:
            ids = self._MARKER.findall(sentence)

            if ids and not self._MARKER.sub("", sentence).strip():
                return f"[cite:{ids[0]}] stands alone; put it right after the words it supports."

        return None


case = Case()
