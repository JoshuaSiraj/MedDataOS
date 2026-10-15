"""UI server. Open one folder with datactrl and ask the agent at --agent-url."""

from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import dispatch
import routes
from case import case
from state import APP_ROOT, state


load_dotenv(APP_ROOT / ".env")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    dispatch.fill_card()
    yield


app = FastAPI(title="MedDataOS", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(routes.FRONTEND)), name="static")
app.include_router(routes.router)


def log_launch(root: Path, shown: str, port: int) -> None:
    """Print the opened case and where to reach it. Flushed so it shows before uvicorn."""
    report = state.report or {}
    counts = report.get("counts") or {}

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

    print(f"Agent: {state.agent_url} model={os.getenv('AGENT_MODEL') or '?'}", flush=True)
    print(f"Tools: {', '.join(case.tool_names)}", flush=True)
    print(f"Web UI: http://{shown}:{port}/?patient={quote(root.name)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="MedDataOS")
    parser.add_argument("folder", help="Case folder to open")
    parser.add_argument(
        "--agent-url",
        required=True,
        help="OpenAI-compatible base URL, the part before /chat/completions",
    )
    args = parser.parse_args()

    state.agent_url = args.agent_url.rstrip("/")
    root = state.open(args.folder)
    app.mount("/case", StaticFiles(directory=str(root)), name="case")

    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host

    log_launch(root, shown, port)

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
