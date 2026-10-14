"""Run the real server on a small case folder and talk to it like the page and an agent."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from websockets.sync.client import connect


APP = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def case_folder(tmp_path_factory) -> Path:
    folder = tmp_path_factory.mktemp("cases") / "P0042"
    folder.mkdir()
    (folder / "clinic_note.txt").write_text("Chief complaint: fatigue.\nPlan: follow-up in 2 weeks.\n")
    (folder / "labs.csv").write_text("test,value\nhemoglobin,13.1\nwbc,6.2\n")
    return folder


@pytest.fixture(scope="module")
def server(case_folder):
    port = _free_port()
    env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(port)}
    process = subprocess.Popen(
        [sys.executable, str(APP / "web" / "backend" / "server.py"), str(case_folder)],
        cwd=APP,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"

    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("server did not start")

        yield {"http": base, "ws": f"ws://127.0.0.1:{port}"}

    finally:
        process.terminate()
        process.wait(timeout=10)


def get(server, path):
    with urllib.request.urlopen(server["http"] + path) as response:
        return json.load(response)


def post(server, path, body):
    request = urllib.request.Request(
        server["http"] + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request) as response:
        return json.load(response)


def send_chat(server, message, patient_id="P0042"):
    form = urllib.parse.urlencode({"message": message, "patient_id": patient_id}).encode()

    with urllib.request.urlopen(server["http"] + "/api/chat", data=form) as response:
        return json.load(response)


def wait_for_answer(server, session_id, timeout=10):
    deadline = time.time() + timeout

    while time.time() < deadline:
        session = get(server, f"/api/session/{session_id}")

        if not session["processing"]:
            return session

        time.sleep(0.1)

    raise AssertionError("no answer arrived")


def test_page_is_served(server):
    with urllib.request.urlopen(server["http"] + "/") as response:
        assert response.status == 200
        assert b"MedDataOS" in response.read()


def test_patient_card_comes_from_the_folder(server):
    patients = get(server, "/api/patients")

    assert [patient["id"] for patient in patients] == ["P0042"]
    assert [item["label"] for item in patients[0]["modalities"]] == ["Notes", "Tables"]


def test_case_files_are_served(server):
    with urllib.request.urlopen(server["http"] + "/case/clinic_note.txt") as response:
        assert b"fatigue" in response.read()


def test_tool_list_hides_server_arguments(server):
    tools = get(server, "/api/agent/tools")

    assert "fetch" in [tool["function"]["name"] for tool in tools]

    for tool in tools:
        params = tool["function"]["parameters"]
        assert "root" not in params["properties"]
        assert "case_id" not in params["properties"]
        assert "root" not in params["required"]


def test_tools_run_on_the_open_folder(server, case_folder):
    discovered = post(server, "/api/agent/tool", {"name": "discover", "arguments": {"root": "/tmp"}})

    assert discovered["status"] == "ok"
    assert discovered["result"]["root"] == str(case_folder)

    note_id = discovered["result"]["notes"][0]["id"]
    fetched = post(server, "/api/agent/tool", {
        "name": "fetch",
        "arguments": {"resource_id": note_id, "view": "text"},
    })

    assert fetched["status"] == "ok"
    assert "fatigue" in fetched["result"]["data"]["text"]


def test_tool_errors_come_back_as_results(server):
    assert post(server, "/api/agent/tool", {"name": "nope", "arguments": {}})["status"] == "error"
    assert post(server, "/api/agent/tool", {"name": "describe", "arguments": {}})["status"] == "error"


def test_agent_socket_sends_tools_then_runs_calls(server):
    with connect(server["ws"] + "/ws/agent") as sock:
        first = json.loads(sock.recv(timeout=5))
        assert first["type"] == "tools"
        assert "describe or fetch" in first["citation"]["when"]

        sock.send(json.dumps({"type": "tool", "name": "discover", "arguments": {}}))
        result = json.loads(sock.recv(timeout=5))
        assert result["type"] == "tool_result"
        assert result["status"] == "ok"


def test_chat_round_trip_over_http(server):
    session_id = send_chat(server, "What labs are there?")["session_id"]

    pending = {item["session_id"]: item for item in get(server, "/api/agent/pending")}
    query = pending[session_id]
    assert query["message"] == "What labs are there?"
    assert "/case/labs.csv" in [item["web_path"] for item in query["case"]["resources"]]
    assert "[cite:1]" in query["citation"]["example"]["response"]

    with connect(server["ws"] + "/ws") as page:
        assert json.loads(page.recv(timeout=5))["type"] == "system"
        assert post(server, "/api/agent/reply", {
            "session_id": session_id,
            "message": "Hemoglobin and WBC.",
        })["status"] == "ok"
        pushed = json.loads(page.recv(timeout=5))

    assert pushed["type"] == "assistant"
    assert pushed["session_id"] == session_id

    answer = wait_for_answer(server, session_id)["history"][-1]
    assert answer["role"] == "assistant"
    assert answer["content"] == "Hemoglobin and WBC."


def test_tool_reads_are_scoped_to_one_session(server):
    first = send_chat(server, "Read the note.")["session_id"]
    second = send_chat(server, "Answer without reading.")["session_id"]
    pending = {item["session_id"]: item for item in get(server, "/api/agent/pending")}
    note = next(item for item in pending[first]["case"]["resources"] if item["modality"] == "note")

    fetched = post(server, "/api/agent/tool", {
        "name": "fetch",
        "session_id": first,
        "arguments": {"resource_id": note["id"], "view": "text"},
    })
    assert fetched["status"] == "ok"

    assert post(server, "/api/agent/reply", {
        "session_id": second,
        "message": "No files opened.",
    })["status"] == "ok"
    assert post(server, "/api/agent/reply", {
        "session_id": first,
        "message": "Fatigue.",
    })["status"] == "error"

    cited = json.dumps({
        "response": "The note records fatigue [cite:1].",
        "citations": [{
            "id": "1",
            "file": "clinic_note.txt",
            "web_path": note["web_path"],
            "summary": "Chief complaint: fatigue.",
        }],
    })
    assert post(server, "/api/agent/reply", {
        "session_id": first,
        "message": cited,
    })["status"] == "ok"


def test_opened_files_require_a_citation(server):
    session_id = send_chat(server, "What does the note say?")["session_id"]
    pending = {item["session_id"]: item for item in get(server, "/api/agent/pending")}
    note = next(item for item in pending[session_id]["case"]["resources"] if item["modality"] == "note")
    web_path = note["web_path"]

    assert post(server, "/api/agent/tool", {
        "name": "fetch",
        "arguments": {"resource_id": note["id"], "view": "text"},
    })["status"] == "ok"

    refused = post(server, "/api/agent/reply", {"session_id": session_id, "message": "Fatigue."})
    assert refused["status"] == "error"
    assert web_path in refused["message"]
    assert get(server, f"/api/session/{session_id}")["processing"] is True

    clumped = json.dumps({
        "response": "The note records fatigue [cite:1][cite:1].",
        "citations": [{
            "id": "1",
            "file": "clinic_note.txt",
            "web_path": web_path,
            "summary": "Chief complaint: fatigue.",
        }],
    })
    assert post(server, "/api/agent/reply", {"session_id": session_id, "message": clumped})["status"] == "error"
    assert get(server, f"/api/session/{session_id}")["processing"] is True

    cited = json.dumps({
        "response": "The note records fatigue [cite:1].",
        "citations": [{
            "id": "1",
            "file": "clinic_note.txt",
            "web_path": web_path,
            "summary": "Chief complaint: fatigue.",
        }],
    })
    assert post(server, "/api/agent/reply", {"session_id": session_id, "message": cited})["status"] == "ok"

    answer = wait_for_answer(server, session_id)["history"][-1]
    assert answer["content"] == cited


def test_example_agent_requires_a_model():
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_MODEL"}
    env["OPENAI_MODEL"] = ""
    result = subprocess.run(
        [sys.executable, str(APP / "examples" / "agent.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "OPENAI_MODEL" in result.stderr
