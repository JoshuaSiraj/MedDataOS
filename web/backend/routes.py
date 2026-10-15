"""Web routes: the page and its socket, chat, and the sidebar data."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

import dispatch
from case import case
from state import APP_ROOT, log, short_session, state


router = APIRouter()

FRONTEND = APP_ROOT / "web" / "frontend"


@router.get("/")
async def read_root():
    return FileResponse(
        str(FRONTEND / "index.html"),
        headers={"Cache-Control": "no-cache"},
    )


@router.websocket("/ws")
async def browser_socket(websocket: WebSocket):
    await websocket.accept()
    state.hub.connect(websocket)
    log("page", f"connected ({len(state.hub.connections)} open)")
    reason = ""

    try:
        await websocket.send_json({
            "type": "system",
            "message": "Connected to MedDataOS",
            "timestamp": "",
        })

        card = case.patient()

        if state.profile and card:
            await websocket.send_json({"type": "patient", "patient": card.as_dict()})

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        reason = f": {exc}"
    finally:
        state.hub.disconnect(websocket)
        log("page", f"disconnected ({len(state.hub.connections)} open){reason}")


@router.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "case": str(state.root) if state.root else None,
        "active_connections": len(state.hub.connections),
        "active_sessions": len(state.sessions),
    }


UPLOAD_TYPES = (".csv", ".xlsx")


async def _save_upload(file: UploadFile) -> Path:
    """Save an uploaded table to data/input. Raises ValueError for other file types."""
    name = (file.filename or "").lower()

    if not name.endswith(UPLOAD_TYPES):
        raise ValueError("Only CSV and Excel (.csv, .xlsx) files are allowed")

    dest = APP_ROOT / "data" / "input" / f"dataset{Path(name).suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        dest.write_bytes(await file.read())
    except OSError as exc:
        raise ValueError(f"Failed to save file: {exc}") from exc
    finally:
        await file.close()

    return dest


@router.post("/api/chat")
async def chat(
    message: str = Form(...),
    session_id: str | None = Form(None),
    patient_id: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    message = message.strip()

    if not message:
        return {"status": "error", "message": "Message is required"}

    if session_id not in state.sessions:
        session_id = state.new_session(patient_id)

    session = state.sessions[session_id]
    label = short_session(session_id)

    if patient_id and session.patient_id in (None, patient_id):
        session.patient_id = patient_id

    if session.processing:
        log("user", f"session={label} still waiting on the previous question")
        return {
            "status": "error",
            "message": "Session is currently processing a request. Please wait.",
            "session_id": session_id,
        }

    if file:
        try:
            session.uploaded_file = str(await _save_upload(file))
        except ValueError as exc:
            return {"status": "error", "message": str(exc), "session_id": session_id}

        message += f"\n[Uploaded file: {file.filename}]"

    session.processing = True
    session.add("user", message)
    log("user", f"session={label} patient={session.patient_id or '?'} {message}")

    dispatch.ask(session_id)
    return {"status": "processing", "session_id": session_id}


@router.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = state.sessions.get(session_id)

    if session is None:
        return {"status": "error", "message": "Session not found"}

    return {
        "status": "success",
        "session_id": session_id,
        "message_count": len(session.history),
        "processing": session.processing,
        "history": session.history,
    }


@router.get("/api/patients")
async def list_patients():
    found = case.patient()
    return [found.as_dict()] if found else []


@router.get("/api/patients/{patient_id}/conversations")
async def list_conversations(patient_id: str):
    return state.conversations(patient_id)


@router.post("/api/patients/{patient_id}/conversations")
async def create_conversation(patient_id: str):
    session_id = state.new_session(patient_id)
    return {"session_id": session_id, "patient_id": patient_id}


@router.get("/api/patients/{patient_id}/pins")
async def list_pins(patient_id: str):
    return state.pins.get(patient_id, [])


def _same_citation(pin: dict, citation: dict) -> bool:
    pinned = pin.get("citation") or {}
    return (
        pin.get("type", "citation") == "citation"
        and pinned.get("agent") == citation.get("agent")
        and pinned.get("web_path") == citation.get("web_path")
    )


def _same_text(pin: dict, text: str) -> bool:
    return pin.get("type") == "text" and pin.get("text") == text


@router.post("/api/patients/{patient_id}/pins")
async def add_pin(patient_id: str, request: dict):
    pin_type = request.get("type", "citation")
    pins = state.pins.setdefault(patient_id, [])

    if pin_type == "citation":
        citation = request.get("citation")

        if not citation:
            return {"status": "error", "message": "citation is required"}

        duplicate = next((pin for pin in pins if _same_citation(pin, citation)), None)
        pin = {
            "type": "citation",
            "citation": citation,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query": request.get("query", ""),
            "annotations": {"text": "", "tags": []},
        }

    elif pin_type == "text":
        text = request.get("text", "").strip()

        if not text:
            return {"status": "error", "message": "text is required"}

        duplicate = next((pin for pin in pins if _same_text(pin, text)), None)
        pin = {"type": "text", "text": text}

    else:
        return {"status": "error", "message": "invalid pin type"}

    if duplicate:
        return {"status": "duplicate", "pin_id": duplicate["pin_id"]}

    pin_id = str(uuid4())
    pins.append({"pin_id": pin_id, **pin, "source": request.get("source", "")})
    return {"status": "ok", "pin_id": pin_id}


@router.delete("/api/patients/{patient_id}/pins/{pin_id}")
async def remove_pin(patient_id: str, pin_id: str):
    pins = state.pins.get(patient_id, [])
    state.pins[patient_id] = [pin for pin in pins if pin["pin_id"] != pin_id]
    return {"status": "ok"}


@router.patch("/api/patients/{patient_id}/pins/{pin_id}")
async def patch_pin(patient_id: str, pin_id: str, request: dict):
    pin = next((pin for pin in state.pins.get(patient_id, []) if pin["pin_id"] == pin_id), None)

    if pin is None:
        return {"status": "error", "message": "Pin not found"}

    if "annotations" in request:
        pin["annotations"] = request["annotations"]

    return pin


@router.get("/api/patients/{patient_id}/reviews")
async def list_reviews(patient_id: str):
    return state.reviews.get(patient_id, {})


@router.patch("/api/patients/{patient_id}/reviews")
async def patch_review(patient_id: str, request: dict):
    key = request.get("key", "").strip()

    if not key:
        return JSONResponse(status_code=422, content={"error": "key is required"})

    checklist_state = request.get("checklist_state", {})
    state.reviews.setdefault(patient_id, {})[key] = checklist_state

    return {"key": key, "checklist_state": checklist_state}
