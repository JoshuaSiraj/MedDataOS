"""User messages. The page posts here; an outside agent answers."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from log import log
from log import session as short_session
from routers.agents import push_query
from state import APP_ROOT, state


router = APIRouter()


def _save_upload(file: UploadFile) -> str:
    upload_dir = APP_ROOT / "data" / "input"
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = ".csv" if file.filename and file.filename.lower().endswith(".csv") else ".xlsx"
    dest = upload_dir / f"dataset{extension}"
    return str(dest)


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

    if not session_id or session_id not in state.sessions:
        session_id = state.new_session(patient_id)

    session = state.sessions[session_id]
    current_patient = session.get("patient_id")

    if patient_id and (not current_patient or current_patient == patient_id):
        session["patient_id"] = patient_id

    if session["processing"]:
        log("user", f"session={short_session(session_id)} still waiting on the previous question")
        return {
            "status": "error",
            "message": "Session is currently processing a request. Please wait.",
            "session_id": session_id,
        }

    if file:
        if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx")):
            return {
                "status": "error",
                "message": "Only CSV and Excel (.csv, .xlsx) files are allowed",
                "session_id": session_id,
            }

        dest = Path(_save_upload(file))

        try:
            dest.write_bytes(await file.read())
            session["uploaded_file"] = str(dest)
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Failed to save file: {exc}",
                "session_id": session_id,
            }
        finally:
            await file.close()

    session["processing"] = True

    user_message = message
    if file and file.filename:
        user_message += f"\n[Uploaded file: {file.filename}]"

    session["history"].append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    log("user", f"session={short_session(session_id)} patient={session.get('patient_id') or '?'} {user_message}")

    await push_query(session_id)

    return {"status": "processing", "session_id": session_id}


@router.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = state.sessions.get(session_id)

    if session is None:
        return {"status": "error", "message": "Session not found"}

    return {
        "status": "success",
        "session_id": session_id,
        "message_count": len(session["history"]),
        "processing": session["processing"],
        "history": session["history"],
    }
