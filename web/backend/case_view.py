"""Turn the datactrl discover report into the patient card the page already expects."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from state import state


def web_path(relative: str) -> str:
    parts = [quote(part) for part in Path(relative).parts if part not in ("", ".")]
    return "/case/" + "/".join(parts)


def profile() -> dict:
    """Demographics from a JSON note, when one has a name."""
    if state.report is None or state.root is None:
        return {}

    for ref in state.report.get("notes", []):
        path = ref.get("path", "")

        if not path.lower().endswith(".json"):
            continue

        try:
            data = json.loads((state.root / path).read_text())
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(data, dict) and data.get("name"):
            return data

    return {}


def modalities() -> list[dict]:
    if state.report is None:
        return []

    found = []

    if state.report.get("notes"):
        found.append({"label": "Notes", "date": None})

    if state.report.get("structured"):
        found.append({"label": "Tables", "date": None})

    if state.report.get("dicom"):
        found.append({"label": "DICOM", "date": None})

    return found


def patient() -> dict | None:
    if state.root is None:
        return None

    info = profile()

    return {
        "id": state.root.name,
        "name": info.get("name") or state.root.name,
        "age": info.get("age") or "",
        "sex": info.get("sex") or "",
        "blood_type": info.get("blood_type"),
        "allergies": info.get("allergies") or [],
        "conditions": info.get("conditions") or [],
        "modalities": modalities(),
        "data_dates": info.get("data_dates") or {},
    }


CITATION = {
    "when": (
        "Required after describe or fetch while this question is waiting. "
        "Plain text is fine when neither was called."
    ),
    "message": (
        "A JSON string. Put each [cite:id] immediately after the sentence that file supports. "
        "Do not group the markers at the end of the answer. "
        "web_path must be one of the files opened for this question."
    ),
    "example": {
        "response": "The planned dose was 51 Gy [cite:1]. Treatment finished on February 13 [cite:2].",
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
    },
}


def inventory() -> list[dict]:
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


def query_payload(session_id: str) -> dict:
    session = state.sessions[session_id]

    return {
        "type": "query",
        "session_id": session_id,
        "patient_id": session.get("patient_id"),
        "message": session["history"][-1]["content"],
        "history": session["history"],
        "case": {
            "id": state.root.name if state.root else None,
            "root": str(state.root) if state.root else None,
            "resources": inventory(),
        },
        "citation": CITATION,
    }
