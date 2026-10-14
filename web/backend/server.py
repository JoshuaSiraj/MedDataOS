"""UI server. Open one folder with datactrl, then let outside agents reply."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from case_view import patient
from routers import agents, chat, pages, patients
from routers.agents import AGENT_TOOLS
from state import state


app = FastAPI(title="MedDataOS")

frontend_path = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

app.include_router(pages.router)
app.include_router(chat.router)
app.include_router(patients.router)
app.include_router(agents.router)


def log_launch(root: Path, shown: str, port: int) -> None:
    """Print the opened case and where to reach it. Flushed so it shows before uvicorn."""
    report = state.report or {}
    counts = report.get("counts") or {}
    card = patient() or {}

    print(f"Case: {root}", flush=True)
    print(
        "Discovered "
        f"{counts.get('total', 0)} resources "
        f"(notes={counts.get('notes', 0)}, "
        f"tables={counts.get('structured', 0)}, "
        f"dicom={counts.get('dicom', 0)}, "
        f"unknown={counts.get('unknown', 0)})",
        flush=True,
    )

    for ref in report.get("resources") or []:
        modality = ref.get("modality") or "?"
        label = ref.get("label") or ""
        path = ref.get("path") or ""
        print(f"  {modality:<12} {label}  {path}", flush=True)

    for item in report.get("unknown") or []:
        path = item.get("path", "") if isinstance(item, dict) else item
        reason = item.get("reason", "") if isinstance(item, dict) else ""
        print(f"  {'unknown':<12} {path}  {reason}", flush=True)

    names = ", ".join(tool["function"]["name"] for tool in AGENT_TOOLS)

    print(f"Patient: {card.get('name') or root.name}", flush=True)
    print(f"Agents: ws://{shown}:{port}/ws/agent", flush=True)
    print(f"Tools: {names}", flush=True)
    print(f"Web UI: http://{shown}:{port}/?patient={quote(root.name)}", flush=True)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python web/backend/server.py /path/to/folder")

    root = state.open(sys.argv[1])
    app.mount("/case", StaticFiles(directory=str(root)), name="case")

    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host

    log_launch(root, shown, port)

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
