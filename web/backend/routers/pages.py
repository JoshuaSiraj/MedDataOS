"""The page and the browser socket."""

from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from log import log
from state import state


router = APIRouter()

frontend_path = Path(__file__).resolve().parents[2] / "frontend"


@router.get("/")
async def read_root():
    return FileResponse(
        str(frontend_path / "index.html"),
        headers={"Cache-Control": "no-cache"},
    )


@router.websocket("/ws")
async def browser_socket(websocket: WebSocket):
    await websocket.accept()
    state.hub.connect(websocket)
    log("page", f"connected ({len(state.hub.connections)} open)")

    try:
        await websocket.send_json({
            "type": "system",
            "message": "Connected to MedDataOS",
            "timestamp": "",
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        state.hub.disconnect(websocket)
        log("page", f"disconnected ({len(state.hub.connections)} open)")
    except Exception as exc:
        state.hub.disconnect(websocket)
        log("page", f"disconnected ({len(state.hub.connections)} open): {exc}")


@router.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "case": str(state.root) if state.root else None,
        "active_connections": len(state.hub.connections),
        "active_sessions": len(state.sessions),
        "agents_connected": len(state.agents),
    }
