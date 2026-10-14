"""Browser sockets that receive chat replies."""

from __future__ import annotations

import asyncio
from datetime import datetime


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
