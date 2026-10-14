"""Sidebar data: the case, its conversations, pins, and reviews."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from case_view import patient
from state import state


router = APIRouter(prefix="/api/patients")


@router.get("")
async def list_patients():
    found = patient()
    return [found] if found else []


@router.get("/{patient_id}/conversations")
async def list_conversations(patient_id: str):
    return state.conversations(patient_id)


@router.post("/{patient_id}/conversations")
async def create_conversation(patient_id: str):
    session_id = state.new_session(patient_id)
    return {"session_id": session_id, "patient_id": patient_id}


@router.get("/{patient_id}/pins")
async def list_pins(patient_id: str):
    return state.pins.get(patient_id, [])


@router.post("/{patient_id}/pins")
async def add_pin(patient_id: str, request: dict):
    pin_type = request.get("type", "citation")
    pins = state.pins.setdefault(patient_id, [])

    if pin_type == "citation":
        citation = request.get("citation")
        if not citation:
            return {"status": "error", "message": "citation is required"}

        for pin in pins:
            same_agent = pin.get("citation", {}).get("agent") == citation.get("agent")
            same_path = pin.get("citation", {}).get("web_path") == citation.get("web_path")
            if pin.get("type", "citation") == "citation" and same_agent and same_path:
                return {"status": "duplicate", "pin_id": pin["pin_id"]}

        pin_id = str(uuid4())
        pins.append({
            "pin_id": pin_id,
            "type": "citation",
            "citation": citation,
            "source": request.get("source", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query": request.get("query", ""),
            "annotations": {"text": "", "tags": []},
        })

    elif pin_type == "text":
        text = request.get("text", "").strip()
        if not text:
            return {"status": "error", "message": "text is required"}

        for pin in pins:
            if pin.get("type") == "text" and pin.get("text") == text:
                return {"status": "duplicate", "pin_id": pin["pin_id"]}

        pin_id = str(uuid4())
        pins.append({
            "pin_id": pin_id,
            "type": "text",
            "text": text,
            "source": request.get("source", ""),
        })

    else:
        return {"status": "error", "message": "invalid pin type"}

    return {"status": "ok", "pin_id": pin_id}


@router.delete("/{patient_id}/pins/{pin_id}")
async def remove_pin(patient_id: str, pin_id: str):
    pins = state.pins.get(patient_id, [])
    state.pins[patient_id] = [pin for pin in pins if pin["pin_id"] != pin_id]
    return {"status": "ok"}


@router.patch("/{patient_id}/pins/{pin_id}")
async def patch_pin(patient_id: str, pin_id: str, request: dict):
    for pin in state.pins.get(patient_id, []):
        if pin["pin_id"] == pin_id:
            if "annotations" in request:
                pin["annotations"] = request["annotations"]
            return pin

    return {"status": "error", "message": "Pin not found"}


@router.get("/{patient_id}/reviews")
async def list_reviews(patient_id: str):
    return state.reviews.get(patient_id, {})


@router.patch("/{patient_id}/reviews")
async def patch_review(patient_id: str, request: dict):
    key = request.get("key", "").strip()

    if not key:
        return JSONResponse(status_code=422, content={"error": "key is required"})

    checklist_state = request.get("checklist_state", {})
    state.reviews.setdefault(patient_id, {})[key] = checklist_state

    return {"key": key, "checklist_state": checklist_state}
