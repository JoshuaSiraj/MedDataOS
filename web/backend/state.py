"""Process state for the one open case and the in-memory UI."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from datactrl import tools

from hub import Hub


APP_ROOT = Path(__file__).resolve().parents[2]


class AppState:
    """The case, chat sessions, and sockets for this process."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self.report: dict | None = None
        self.sessions: dict[str, dict] = {}
        self.pins: dict[str, list] = {}
        self.reviews: dict[str, dict] = {}
        self.agents: set = set()
        self.pending: dict[str, dict] = {}
        self.reads: dict[str, list] = {}
        self.hub = Hub()

    def open(self, folder: str) -> Path:
        """Open ``folder`` with datactrl. One folder for the life of the process."""
        root = Path(folder).expanduser().resolve()

        if not root.is_dir():
            raise SystemExit(f"Not a folder: {root}")

        print(f"Opening {root}", flush=True)
        self.root = root
        self.report = tools.discover(str(root))
        return root

    def new_session(self, patient_id: str | None) -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = {
            "history": [],
            "processing": False,
            "uploaded_file": None,
            "patient_id": patient_id,
        }
        return session_id

    def conversations(self, patient_id: str) -> list[dict]:
        found = []

        for session_id, session in self.sessions.items():
            if session.get("patient_id") != patient_id:
                continue

            preview = ""
            for message in session["history"]:
                if message["role"] == "user":
                    preview = message["content"][:60]
                    break

            found.append({
                "session_id": session_id,
                "preview": preview or "New conversation",
            })

        return found


state = AppState()
