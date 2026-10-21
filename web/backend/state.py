"""Process state for the one open case: chat sessions, page sockets, and logging."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from datactrl import tools


def log(who: str, message: str) -> None:
    text = " ".join(message.split())

    if len(text) > 180:
        text = text[:177] + "..."

    print(f"{who:<6} {text}", flush=True)


def short_session(session_id: str) -> str:
    return session_id[:8] if session_id else "?"


@dataclass
class Session:
    """One conversation: its messages and whether a question is still being answered."""

    patient_id: str | None = None
    history: list[dict] = field(default_factory=list)
    processing: bool = False
    uploaded_file: str | None = None

    def add(self, role: str, content: str) -> None:
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


class Hub:
    def __init__(self) -> None:
        self.connections: set = set()

    def connect(self, websocket) -> None:
        self.connections.add(websocket)

    def disconnect(self, websocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        if not self.connections:
            return

        await asyncio.gather(
            *[self._send(connection, message) for connection in list(self.connections)],
            return_exceptions=True,
        )

    async def assistant(self, session_id: str, message: str) -> None:
        """Push an agent reply to every open page."""
        await self.broadcast({
            "type": "assistant",
            "session_id": session_id,
            "header": "System Response",
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "metadata": {},
        })

    async def _send(self, connection, message: dict) -> None:
        try:
            await connection.send_json(message)
        except Exception:
            self.connections.discard(connection)


APP_ROOT = Path(__file__).resolve().parents[2]


class AppState:
    """The case, chat sessions, and sockets for this process."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self.report: dict | None = None
        self.profile: dict = {}
        self.sessions: dict[str, Session] = {}
        self.pins: dict[str, list] = {}
        self.reviews: dict[str, dict] = {}
        self.agent_url: str | None = None
        self.specialists: dict = {}
        self.consulted: dict[str, dict[str, dict]] = {}
        self.pending: set[str] = set()
        self.reads: dict[str, list[dict]] = {}
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
        self.sessions[session_id] = Session(patient_id=patient_id)
        return session_id

    def conversations(self, patient_id: str) -> list[dict]:
        found = []

        for session_id, session in self.sessions.items():
            if session.patient_id != patient_id:
                continue

            preview = next(
                (
                    message["content"][:60]
                    for message in session.history
                    if message["role"] == "user"
                ),
                "",
            )
            found.append({
                "session_id": session_id,
                "preview": preview or "New conversation",
            })

        return found


state = AppState()
