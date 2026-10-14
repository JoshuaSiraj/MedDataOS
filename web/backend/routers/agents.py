"""Outside agents. They query the open case, then send a reply."""

import asyncio
import copy
import json
import re
from datetime import datetime, timezone

from datactrl.tools import TOOL_DEFINITIONS, dispatch
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from case_view import CITATION, inventory, query_payload
from log import log
from log import session as short_session
from state import state


router = APIRouter()

SERVER_ARGS = ("root", "case_id")


class Reply(BaseModel):
    session_id: str
    message: str


class ToolCall(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)
    session_id: str | None = None


def _for_agents(tool: dict) -> dict:
    """The datactrl tool, without the arguments the server fills in."""
    spec = copy.deepcopy(tool)
    params = spec["function"]["parameters"]

    for key in SERVER_ARGS:
        params.get("properties", {}).pop(key, None)

    params["required"] = [key for key in params.get("required", []) if key not in SERVER_ARGS]
    return spec


AGENT_TOOLS = [_for_agents(tool) for tool in TOOL_DEFINITIONS]

READ_TOOLS = {"describe", "fetch"}

TAKES_ROOT = {
    tool["function"]["name"]
    for tool in TOOL_DEFINITIONS
    if "root" in tool["function"]["parameters"].get("properties", {})
}


def run_tool(call: ToolCall) -> dict:
    """Run one datactrl tool on the folder this server opened."""
    args = {key: value for key, value in call.arguments.items() if key not in SERVER_ARGS}

    if call.name in TAKES_ROOT:
        args["root"] = str(state.root)

    detail = _tool_detail(call)

    try:
        result = json.loads(dispatch(call.name, args))
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        log("agent", f"tool {call.name} {detail} error: {message}")
        return {
            "type": "tool_result",
            "status": "error",
            "name": call.name,
            "message": message,
        }

    _remember_read(call)
    log("agent", f"tool {call.name} {detail} ok")

    return {
        "type": "tool_result",
        "status": "ok",
        "name": call.name,
        "result": result,
    }


def _tool_detail(call: ToolCall) -> str:
    shown = {
        key: value
        for key, value in call.arguments.items()
        if key not in SERVER_ARGS and value is not None
    }
    return " ".join(f"{key}={value}" for key, value in shown.items())


def _remember_read(call: ToolCall) -> None:
    """Remember a file opened while a question is waiting for an answer."""
    if call.name not in READ_TOOLS or not state.pending:
        return

    resource_id = call.arguments.get("resource_id")
    ref = next((item for item in inventory() if item["id"] == resource_id), None)

    if ref is None:
        return

    session_id = call.session_id

    # Keep the HTTP API convenient for a single waiting query while avoiding
    # attributing one agent's reads to every concurrent session.
    if session_id is None and len(state.pending) == 1:
        session_id = next(iter(state.pending))

    if session_id not in state.pending:
        return

    opened = state.reads.setdefault(session_id, [])

    if any(item["web_path"] == ref["web_path"] for item in opened):
        return

    opened.append(ref)


def _citation_error(session_id: str, message: str) -> str | None:
    """A question that opened files must cite at least one of them."""
    opened = state.reads.get(session_id) or []

    if not opened:
        return None

    paths = ", ".join(item["web_path"] for item in opened)
    expected = (
        f"{CITATION['when']} {CITATION['message']} "
        f"Example: {json.dumps(CITATION['example'])} "
        f"Opened files: {paths}"
    )

    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        return expected

    response = parsed.get("response") if isinstance(parsed, dict) else None
    citations = parsed.get("citations") if isinstance(parsed, dict) else None

    if not isinstance(response, str) or not isinstance(citations, list):
        return expected

    opened_paths = {item["web_path"] for item in opened}

    for citation in citations:
        if not isinstance(citation, dict):
            continue

        cite_id = citation.get("id")
        path = citation.get("web_path")
        file_name = citation.get("file")
        summary = citation.get("summary")

        if path not in opened_paths:
            continue

        if not isinstance(cite_id, str) or not re.fullmatch(r"\w+", cite_id):
            continue

        if not isinstance(file_name, str) or not file_name:
            continue

        if not isinstance(summary, str):
            continue

        if f"[cite:{cite_id}]" in response:
            matched = True
            break
    else:
        matched = False

    if not matched or not _markers_are_inline(response):
        return expected

    return None


def _markers_are_inline(response: str) -> bool:
    """Each marker sits in its own sentence, next to the words it supports."""
    sentences = [part.strip() for part in re.split(r"[.!?]+", response) if part.strip()]
    found = []

    for sentence in sentences:
        ids = re.findall(r"\[cite:(\w+)\]", sentence)

        if not ids:
            continue

        if len(ids) != 1:
            return False

        prose = re.sub(r"\[cite:\w+\]", "", sentence).strip()

        if not prose:
            return False

        found.append(ids[0])

    return found == re.findall(r"\[cite:(\w+)\]", response) and bool(found)


async def push_query(session_id: str) -> None:
    payload = query_payload(session_id)
    state.pending[session_id] = payload

    dead = []

    for sock in list(state.agents):
        try:
            await sock.send_json(payload)
        except Exception:
            dead.append(sock)

    for sock in dead:
        state.agents.discard(sock)

    waiting = len(state.agents)
    question = payload["message"]

    if waiting:
        log("server", f"session={short_session(session_id)} question sent to {waiting} agent(s): {question}")
    else:
        log("server", f"session={short_session(session_id)} question held, no agent connected: {question}")


def _reply_preview(message: str) -> str:
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict) and isinstance(parsed.get("response"), str):
        citations = parsed.get("citations")
        count = len(citations) if isinstance(citations, list) else 0
        return f"{count} citation(s): {parsed['response']}"

    return message


async def deliver_reply(session_id: str, message: str) -> dict:
    session = state.sessions.get(session_id)
    label = short_session(session_id)

    if session is None:
        log("agent", f"session={label} reply refused: unknown session")
        return {"status": "error", "message": "Unknown session"}

    citation_error = _citation_error(session_id, message)

    if citation_error:
        log("agent", f"session={label} reply refused, citation required")
        return {"status": "error", "message": citation_error}

    state.reads.pop(session_id, None)

    session["history"].append({
        "role": "assistant",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    session["processing"] = False
    state.pending.pop(session_id, None)

    await state.hub.assistant(session_id, message)
    log(
        "server",
        f"session={label} answer sent to {len(state.hub.connections)} page(s): {_reply_preview(message)}",
    )

    return {"status": "ok", "session_id": session_id}


@router.websocket("/ws/agent")
async def agent_socket(websocket: WebSocket):
    await websocket.accept()
    state.agents.add(websocket)
    log("agent", f"connected ({len(state.agents)} open), {len(AGENT_TOOLS)} tools, {len(state.pending)} waiting question(s)")

    try:
        await websocket.send_json({
            "type": "tools",
            "tools": AGENT_TOOLS,
            "citation": CITATION,
        })

        for payload in list(state.pending.values()):
            await websocket.send_json(payload)

        while True:
            data = json.loads(await websocket.receive_text())
            kind = data.get("type")

            if kind == "tool":
                try:
                    call = ToolCall.model_validate(data)
                except ValidationError as exc:
                    log("agent", f"tool refused: {exc}")
                    await websocket.send_json({
                        "type": "tool_result",
                        "status": "error",
                        "message": str(exc),
                    })
                    continue

                await websocket.send_json(await asyncio.to_thread(run_tool, call))
                continue

            if kind != "reply":
                log("agent", f"ignored message type={kind!r}")
                await websocket.send_json({
                    "status": "error",
                    "message": "Expected type reply or tool",
                })
                continue

            result = await deliver_reply(data.get("session_id", ""), data.get("message", ""))
            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass
    finally:
        state.agents.discard(websocket)
        log("agent", f"disconnected ({len(state.agents)} open)")


@router.get("/api/agent/tools")
async def tools():
    return AGENT_TOOLS


@router.get("/api/agent/pending")
async def pending():
    return list(state.pending.values())


@router.post("/api/agent/reply")
async def reply(body: Reply):
    return await deliver_reply(body.session_id, body.message)


@router.post("/api/agent/tool")
async def tool(body: ToolCall):
    return await asyncio.to_thread(run_tool, body)
