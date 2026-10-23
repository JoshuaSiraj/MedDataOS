"""Run the real server on a small case folder and talk to it like the page and an agent."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


@contextmanager
def running_server(
    case_folder,
    agent_url="http://127.0.0.1:9/v1",
    specialists=None,
    agents_file=None,
    **settings,
):
    port = _free_port()
    env = {key: value for key, value in os.environ.items() if key != "AGENT_URL"}
    env.update(HOST="127.0.0.1", PORT=str(port), **settings)
    command = [
        sys.executable,
        str(APP / "web" / "backend" / "server.py"),
        str(case_folder),
        "--agent-url",
        agent_url,
    ]

    if agents_file:
        command.extend(["--agents", agents_file])

    for specialist in specialists or []:
        command.extend(["--specialist", specialist])

    process = subprocess.Popen(
        command,
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


@pytest.fixture(scope="module")
def server(case_folder):
    with running_server(case_folder) as running:
        yield running


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


def test_a_case_without_dicom_has_no_previews(server):
    assert get(server, "/api/dicom/previews") == []
    request = urllib.request.Request(
        server["http"] + "/api/dicom/preview?web_path=/case/clinic_note.txt"
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request)
    assert caught.value.code == 404


def test_patient_card_comes_from_the_folder(server):
    patients = get(server, "/api/patients")

    assert [patient["id"] for patient in patients] == ["P0042"]
    assert [item["label"] for item in patients[0]["modalities"]] == ["Notes", "Tables"]


def test_case_files_are_served(server):
    with urllib.request.urlopen(server["http"] + "/case/clinic_note.txt") as response:
        assert b"fatigue" in response.read()


def test_server_requires_an_agent_url(case_folder):
    result = subprocess.run(
        [sys.executable, str(APP / "web" / "backend" / "server.py"), str(case_folder)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "--agent-url" in result.stderr


def test_example_agent_requires_a_model():
    env = {key: value for key, value in os.environ.items() if key != "OPENAI_MODEL"}
    env["OPENAI_MODEL"] = ""

    for key in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"):
        env[key] = ""

    result = subprocess.run(
        [sys.executable, str(APP / "examples" / "agent.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "OPENAI_MODEL" in result.stderr


def test_example_agent_forwards_chat_completions():
    class RecordingModel(BaseHTTPRequestHandler):
        requests: list[dict] = []

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            RecordingModel.requests.append(body)
            data = json.dumps({
                "choices": [{"message": {"role": "assistant", "content": "Plain answer."}}],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    RecordingModel.requests = []
    model = ThreadingHTTPServer(("127.0.0.1", 0), RecordingModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    port = _free_port()
    env = {
        **os.environ,
        "OPENAI_MODEL": "real-model",
        "OPENAI_BASE_URL": f"http://127.0.0.1:{model.server_address[1]}/v1",
        "OPENAI_API_KEY": "secret",
        "AZURE_OPENAI_API_KEY": "",
        "AZURE_OPENAI_ENDPOINT": "",
        "AZURE_OPENAI_DEPLOYMENT": "",
    }
    agent = subprocess.Popen(
        [sys.executable, str(APP / "examples" / "agent.py"), "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    example = {"http": f"http://127.0.0.1:{port}"}

    try:
        deadline = time.time() + 5
        while True:
            try:
                sent = post(example, "/v1/chat/completions", {
                    "model": "example",
                    "messages": [{"role": "user", "content": "Say hello."}],
                    "tools": [{"type": "function", "function": {"name": "fetch"}}],
                    "response_format": {"type": "json_schema", "json_schema": {"name": "cited_answer"}},
                })
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.05)

        assert sent["choices"][0]["message"]["content"] == "Plain answer."
        forwarded = RecordingModel.requests[-1]
        assert forwarded["model"] == "real-model"
        assert forwarded["tools"][0]["function"]["name"] == "fetch"
        assert forwarded["response_format"]["json_schema"]["name"] == "cited_answer"
    finally:
        agent.terminate()
        agent.wait(timeout=10)
        model.shutdown()


def cited_note(web_path: str) -> str:
    return json.dumps({
        "response": "The note records fatigue [cite:1].",
        "citations": [{
            "id": "1",
            "file": "clinic_note.txt",
            "web_path": web_path,
            "summary": "Chief complaint: fatigue.",
        }],
    })


def _note_slice(messages: list[dict]) -> dict | None:
    """An exact slice of note text a tool result returned, for the fake agent to cite."""
    for item in reversed(messages):
        if item.get("role") != "tool":
            continue

        try:
            payload = json.loads(item["content"])
        except (TypeError, json.JSONDecodeError):
            continue

        result = payload.get("result") if isinstance(payload, dict) else None
        data = result.get("data") if isinstance(result, dict) else None
        text = data.get("text") if isinstance(data, dict) else None

        if not isinstance(text, str) or not text.strip():
            continue

        line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        start = text.find(line)

        if start < 0 or not line:
            continue

        return {
            "n": 1,
            "claim": "Chief complaint: fatigue.",
            "quote": line,
            "start": start,
            "end": start + len(line),
        }

    return None


def cited_handle(handle: str, messages: list[dict] | None = None) -> str:
    citation: dict = {
        "cite": handle,
        "summary": "Chief complaint: fatigue.",
    }
    evidence = _note_slice(messages or [])

    if evidence:
        citation["evidence"] = [evidence]

    return json.dumps({
        "response": f"The note records fatigue [cite:{handle}].",
        "citations": [citation],
    })


def _cite_handle(messages: list[dict]) -> str:
    for item in reversed(messages):
        if item.get("role") != "tool":
            continue

        try:
            payload = json.loads(item["content"])
        except json.JSONDecodeError:
            continue

        if isinstance(payload.get("cite"), str):
            return payload["cite"]

    return "c1"


CARD = {
    "name": "Jane Doe",
    "age": 64,
    "sex": "F",
    "blood_type": None,
    "allergies": ["Penicillin", 3],
    "conditions": ["Fatigue"],
    "data_dates": {"labs": "2026-01-02", "notes": "last week"},
}


class FakeAgent(BaseHTTPRequestHandler):
    """An OpenAI-compatible endpoint. Tags in the question choose how it behaves."""

    requests: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeAgent.requests.append(body)
        status, payload = self.respond(body)
        data = json.dumps(payload).encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond(self, body: dict) -> tuple[int, dict]:
        messages = body["messages"]
        question = next(item["content"] for item in messages if item["role"] == "user")
        system = messages[0]["content"]
        resources = json.loads(system.split("Case resources: ", 1)[1].split("\n", 1)[0])
        note = next(item for item in resources if item["modality"] == "note")
        has_read = any(item["role"] == "tool" for item in messages)
        corrected = any(
            item["role"] == "user" and item["content"].startswith("The server refused")
            for item in messages
        )

        if question == "Fill in the patient card.":
            return 200, self.message(content="```json\n" + json.dumps(CARD) + "\n```")

        if "[dump]" in question and not corrected:
            return 200, self.message(content=(
                'The scan is a CT [cite:dicom:1.2.3].\n\n'
                '{"response": "The scan is a CT [cite:dicom:1.2.3].", "citations":'
            ))

        if "[dump]" in question:
            return 200, self.message(content=cited_note(note["web_path"]))

        if "[echo]" in question and not corrected:
            return 200, self.message(content='{"when": "Plain text is fine.", "message": ""}')

        if "[wrap]" in question:
            return 200, self.message(content='{"message": "Hello! How can I assist you today?"}')

        if "[broken]" in question:
            return 200, {"oops": True}

        if "[bad args]" in question and not has_read:
            return 200, self.message(tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "fetch", "arguments": "{not json"},
            }])

        if "[no tools]" in question and "tools" in body:
            return 400, {"error": {"message": "tools are not supported"}}

        if "[no schema]" in question and "response_format" in body:
            return 400, {"error": {"message": "response_format is not supported"}}

        if "[discover]" in question and not has_read:
            return 200, self.message(tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {"name": "discover", "arguments": json.dumps({"root": "/tmp"})},
            }])

        if "[read]" in question and not has_read:
            return 200, self.message(tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "fetch",
                    "arguments": json.dumps({"resource_id": note["id"], "view": "text"}),
                },
            }])

        if "[never]" in question or ("[forget]" in question and not corrected):
            return 200, self.message(content="Fatigue.")

        if "[alone]" in question and has_read and not corrected:
            handle = _cite_handle(messages)
            alone = json.dumps({
                "response": f"The note records fatigue. [cite:{handle}]",
                "citations": [{
                    "cite": handle,
                    "summary": "Chief complaint: fatigue.",
                }],
            })
            return 200, self.message(content=alone)

        if "[multi]" in question and has_read and not corrected:
            handle = _cite_handle(messages)
            return 200, self.message(content=json.dumps({
                "response": (
                    f"The CT and the note both record fatigue [cite:{handle}] [cite:{handle}]."
                ),
                "citations": [{
                    "cite": handle,
                    "summary": "Chief complaint: fatigue.",
                }],
            }))

        if "[multi]" in question and has_read:
            handle = _cite_handle(messages)
            citation: dict = {
                "cite": handle,
                "summary": "Chief complaint: fatigue.",
            }
            evidence = _note_slice(messages)

            if evidence:
                citation["evidence"] = [evidence]

            return 200, self.message(content=json.dumps({
                "response": (
                    f"The CT records fatigue [cite:{handle}]. The note records it too [cite:{handle}]."
                ),
                "citations": [citation],
            }))

        if "[discover]" in question and has_read:
            return 200, self.message(content="Discovered.")

        if has_read:
            return 200, self.message(content=f"```json\n{cited_handle(_cite_handle(messages), messages)}\n```")

        return 200, self.message(content="Plain answer.")

    @staticmethod
    def message(**fields) -> dict:
        return {"choices": [{"message": {"role": "assistant", "content": None, **fields}}]}

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def dispatch_server(case_folder):
    agent = ThreadingHTTPServer(("127.0.0.1", 0), FakeAgent)
    threading.Thread(target=agent.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{agent.server_address[1]}/v1"

    try:
        with running_server(case_folder, agent_url=url, AGENT_MODEL="fake") as running:
            yield running
    finally:
        agent.shutdown()


def requests_for(question: str) -> list[dict]:
    return [body for body in FakeAgent.requests if body["messages"][1]["content"] == question]


def test_server_sends_the_question_to_the_agent(dispatch_server):
    question = "Say hello."

    with connect(dispatch_server["ws"] + "/ws") as page:
        assert json.loads(page.recv(timeout=5))["type"] == "system"
        session_id = send_chat(dispatch_server, question)["session_id"]
        pushed = json.loads(page.recv(timeout=5))

        while pushed["type"] == "patient":
            pushed = json.loads(page.recv(timeout=5))

    assert pushed["type"] == "assistant"
    assert pushed["session_id"] == session_id
    assert pushed["message"] == "Plain answer."

    sent = requests_for(question)
    assert len(sent) == 1
    assert sent[0]["model"] == "fake"

    for tool in sent[0]["tools"]:
        params = tool["function"]["parameters"]
        assert "root" not in params.get("properties", {})
        assert "case_id" not in params.get("properties", {})


def test_the_agent_fills_in_the_patient_card(dispatch_server):
    deadline = time.time() + 10

    while time.time() < deadline:
        card = get(dispatch_server, "/api/patients")[0]

        if card["name"] != "P0042":
            break

        time.sleep(0.1)

    assert card["id"] == "P0042"
    assert card["name"] == "Jane Doe"
    assert card["age"] == "64"
    assert card["allergies"] == ["Penicillin"]
    assert card["conditions"] == ["Fatigue"]
    assert card["data_dates"] == {"labs": "2026-01-02"}
    assert [item["label"] for item in card["modalities"]] == ["Notes", "Tables"]

    with connect(dispatch_server["ws"] + "/ws") as page:
        assert json.loads(page.recv(timeout=5))["type"] == "system"
        assert json.loads(page.recv(timeout=5))["patient"]["name"] == "Jane Doe"


def test_the_card_shows_the_folder_name_without_an_agent(server):
    card = get(server, "/api/patients")[0]

    assert card["name"] == "P0042"
    assert card["age"] == ""
    assert card["conditions"] == []


def test_server_reads_the_folder_it_opened(dispatch_server):
    question = "[discover] What is in the folder?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = wait_for_answer(dispatch_server, session_id)["history"][-1]

    assert answer["content"] == "Discovered."
    tool = next(item for item in requests_for(question)[-1]["messages"] if item["role"] == "tool")
    assert json.loads(tool["content"])["result"]["root"].endswith("P0042")


def test_server_rejects_a_marker_that_stands_alone(dispatch_server):
    question = "[read][alone] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert answer["response"].count("[cite:c1]") == 1
    assert any(
        item["role"] == "user" and item["content"].startswith("The server refused")
        for item in requests_for(question)[-1]["messages"]
    )


def test_a_greeting_wrapped_in_json_is_shown_as_text(dispatch_server):
    session_id = send_chat(dispatch_server, "[wrap] Hello")["session_id"]
    answer = wait_for_answer(dispatch_server, session_id)["history"][-1]

    assert answer["content"] == "Hello! How can I assist you today?"


def test_json_without_files_is_sent_back_for_plain_text(dispatch_server):
    question = "[echo] Hello"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = wait_for_answer(dispatch_server, session_id)["history"][-1]

    assert answer["content"] == "Plain answer."
    assert any(
        item["role"] == "user" and "plain text, not JSON" in item["content"]
        for item in requests_for(question)[-1]["messages"]
    )


def test_prose_followed_by_json_is_sent_back_for_a_citation_object(dispatch_server):
    question = "[dump] Have a look at its imaging"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert answer["response"].count("[cite:1]") == 1
    assert any(
        item["role"] == "user" and "only one JSON object" in item["content"]
        for item in requests_for(question)[-1]["messages"]
    )


def test_server_runs_the_agents_tool_calls(dispatch_server):
    session_id = send_chat(dispatch_server, "[read] What does the note say?")["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert "[cite:c1]" in answer["response"]
    citation = answer["citations"][0]
    assert citation["id"] == "c1"
    assert citation["cite"] == "c1"
    assert citation["web_path"].endswith("clinic_note.txt")
    assert citation["command"]["tool"] == "fetch"
    assert citation["command"]["arguments"]["view"] == "text"
    assert citation["command"]["arguments"]["resource_id"]


def test_server_rejects_markers_side_by_side(dispatch_server):
    question = "[read][multi] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert answer["response"] == (
        "The CT records fatigue [cite:c1]. The note records it too [cite:c1]."
    )
    assert any(
        item["role"] == "user" and "side by side" in item["content"]
        for item in requests_for(question)[-1]["messages"]
    )


def test_server_asks_the_agent_to_fix_missing_citations(dispatch_server):
    question = "[read][forget] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert "[cite:c1]" in answer["response"]
    assert any(
        item["role"] == "user" and item["content"].startswith("The server refused")
        for item in requests_for(question)[-1]["messages"]
    )


def test_server_gives_up_after_repeated_bad_citations(dispatch_server):
    session_id = send_chat(dispatch_server, "[read][never] What does the note say?")["session_id"]
    answer = wait_for_answer(dispatch_server, session_id)["history"][-1]

    assert "could not produce an answer" in answer["content"]


def test_server_retries_without_tools_when_the_agent_refuses_them(dispatch_server):
    question = "[no tools] Say hello."
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = wait_for_answer(dispatch_server, session_id)["history"][-1]

    assert answer["content"] == "Plain answer."
    assert ["tools" in body for body in requests_for(question)] == [True, False]


def test_the_answer_schema_is_sent_once_the_agent_has_read(dispatch_server):
    question = "[read] Which schema does the note answer use?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert "[cite:c1]" in answer["response"]
    bodies = requests_for(question)
    assert ["response_format" in body for body in bodies] == [False, True]
    sent = bodies[-1]["response_format"]
    assert sent["type"] == "json_schema"
    assert sent["json_schema"]["strict"] is True
    assert "Answer schema, with examples:" in bodies[0]["messages"][0]["content"]


def test_server_retries_without_the_schema_when_the_agent_refuses_it(dispatch_server):
    question = "[read][no schema] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert "[cite:c1]" in answer["response"]
    assert ["response_format" in body for body in requests_for(question)] == [False, True, False]
    assert all("tools" in body for body in requests_for(question))


def test_bad_tool_arguments_are_returned_to_the_agent(dispatch_server):
    question = "[bad args] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    wait_for_answer(dispatch_server, session_id)

    tool = next(item for item in requests_for(question)[-1]["messages"] if item["role"] == "tool")
    result = json.loads(tool["content"])
    assert result["status"] == "error"
    assert "not valid JSON" in result["message"]


def test_a_reply_that_is_not_a_chat_completion_is_reported(dispatch_server):
    session_id = send_chat(dispatch_server, "[broken] Say hello.")["session_id"]
    answer = wait_for_answer(dispatch_server, session_id)["history"][-1]

    assert "did not return a chat completion" in answer["content"]


def test_an_unreachable_agent_is_reported(server):
    session_id = send_chat(server, "Say hello.")["session_id"]
    answer = wait_for_answer(server, session_id)["history"][-1]

    assert "could not reach" in answer["content"]


def test_server_rejects_a_bad_specialist_name(case_folder):
    result = subprocess.run(
        [
            sys.executable,
            str(APP / "web" / "backend" / "server.py"),
            str(case_folder),
            "--agent-url",
            "http://127.0.0.1:9/v1",
            "--specialist",
            "Notes=http://127.0.0.1:9/v1",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "lowercase" in result.stderr


def _question_bodies(handler, question: str) -> list[dict]:
    return [
        body for body in handler.requests
        if any(
            message.get("role") == "user" and message.get("content") == question
            for message in body.get("messages", [])
        )
    ]


class Router(BaseHTTPRequestHandler):
    """Router fake: calls the specialist named by a tag in the question."""

    requests: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        Router.requests.append(body)
        status, payload = self.respond(body)
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond(self, body: dict) -> tuple[int, dict]:
        messages = body["messages"]
        question = next(item["content"] for item in messages if item["role"] == "user")
        tool_msgs = [item for item in messages if item["role"] == "tool"]

        if question == "Fill in the patient card." and not tool_msgs:
            return 200, FakeAgent.message(content="```json\n" + json.dumps(CARD) + "\n```")

        if not tool_msgs:
            calls = []

            if "[notes]" in question or "[badcite]" in question:
                calls.append(self._consult("notes", "call_notes", question))

            if "[twice]" in question:
                calls.append(self._consult("notes", "call_notes_2", question))

            if "[scan]" in question:
                calls.append(self._consult("imaging", "call_imaging", question))

            if calls:
                return 200, FakeAgent.message(tool_calls=calls)

            return 200, FakeAgent.message(content="Plain answer.")

        parsed = [json.loads(item["content"]) for item in tool_msgs]
        ok = [
            item["result"] for item in parsed
            if item.get("status") == "ok" and isinstance(item.get("result"), str)
        ]
        errors = [item["message"] for item in parsed if item.get("status") == "error"]
        cited = next((item for item in ok if "[cite:" in item), None)

        if cited:
            payload = json.loads(cited)

            if errors:
                payload["response"] = "Imaging specialist failed. " + payload["response"]

            return 200, FakeAgent.message(content=json.dumps(payload))

        if errors:
            return 200, FakeAgent.message(content="Specialist failed: " + errors[0])

        return 200, FakeAgent.message(content="Plain answer.")

    @staticmethod
    def _consult(name: str, call_id: str, question: str) -> dict:
        return {
            "id": call_id,
            "type": "function",
            "function": {
                "name": f"consult_{name}",
                "arguments": json.dumps({"question": question}),
            },
        }

    def log_message(self, *args):
        pass


class NotesSpecialist(BaseHTTPRequestHandler):
    """Returns a citation for the clinic note, or for a file that is not in the case."""

    requests: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        NotesSpecialist.requests.append(body)
        question = next(item["content"] for item in body["messages"] if item["role"] == "user")
        path = "/case/missing.txt" if "[badcite]" in question else "/case/clinic_note.txt"
        data = json.dumps(FakeAgent.message(content=cited_note(path))).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class ImagingSpecialist(BaseHTTPRequestHandler):
    """Always fails, the way a specialist process that is down would."""

    requests: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        ImagingSpecialist.requests.append(json.loads(self.rfile.read(length) or b"{}"))
        data = json.dumps({"error": {"message": "imaging model down"}}).encode()
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def routing_server(case_folder, tmp_path_factory):
    Router.requests = []
    NotesSpecialist.requests = []
    ImagingSpecialist.requests = []
    router = ThreadingHTTPServer(("127.0.0.1", 0), Router)
    notes = ThreadingHTTPServer(("127.0.0.1", 0), NotesSpecialist)
    imaging = ThreadingHTTPServer(("127.0.0.1", 0), ImagingSpecialist)

    for endpoint in (router, notes, imaging):
        threading.Thread(target=endpoint.serve_forever, daemon=True).start()

    config = tmp_path_factory.mktemp("routing") / "agents.toml"
    config.write_text(
        "\n".join([
            "[notes]",
            f'url = "http://127.0.0.1:{notes.server_address[1]}/v1"',
            'description = "Answers from clinical notes."',
            "",
            "[imaging]",
            f'url = "http://127.0.0.1:{imaging.server_address[1]}/v1"',
            'description = "Interprets imaging."',
            "",
        ])
    )

    try:
        with running_server(
            case_folder,
            agent_url=f"http://127.0.0.1:{router.server_address[1]}/v1",
            agents_file=str(config),
            AGENT_MODEL="router",
        ) as running:
            yield running
    finally:
        for endpoint in (router, notes, imaging):
            endpoint.shutdown()


def test_router_cites_notes_and_reports_an_imaging_failure(routing_server):
    question = "[notes][scan] What do the note and the scan show?"
    session_id = send_chat(routing_server, question)["session_id"]
    answer = json.loads(wait_for_answer(routing_server, session_id)["history"][-1]["content"])

    assert "Imaging specialist failed" in answer["response"]
    assert "[cite:1]" in answer["response"]
    assert answer["citations"][0]["web_path"].endswith("clinic_note.txt")

    router_tools = _question_bodies(Router, question)[0]["tools"]
    tool_names = [tool["function"]["name"] for tool in router_tools]
    assert "consult_notes" in tool_names
    assert "consult_imaging" in tool_names
    assert "fetch" in tool_names
    notes_tool = next(tool for tool in router_tools if tool["function"]["name"] == "consult_notes")
    assert notes_tool["function"]["description"] == "Answers from clinical notes."

    notes_call = _question_bodies(NotesSpecialist, question)
    assert len(notes_call) == 1
    specialist_tools = [tool["function"]["name"] for tool in notes_call[0]["tools"]]
    assert "fetch" in specialist_tools
    assert all(not name.startswith("consult_") for name in specialist_tools)
    assert len(_question_bodies(ImagingSpecialist, question)) == 1


def test_a_specialist_is_consulted_once_per_question(routing_server):
    question = "[notes][twice] Read the note twice"
    session_id = send_chat(routing_server, question)["session_id"]
    answer = json.loads(wait_for_answer(routing_server, session_id)["history"][-1]["content"])

    assert answer["citations"][0]["web_path"].endswith("clinic_note.txt")
    assert len(_question_bodies(NotesSpecialist, question)) == 1

    sent_back = next(
        body for body in _question_bodies(Router, question)
        if any(item["role"] == "tool" for item in body["messages"])
    )
    assistant = next(item for item in sent_back["messages"] if item["role"] == "assistant")
    assert [call["function"]["name"] for call in assistant["tool_calls"]] == [
        "consult_notes",
        "consult_notes",
    ]
    tool_messages = [item for item in sent_back["messages"] if item["role"] == "tool"]
    assert len(tool_messages) == 2
    assert json.loads(tool_messages[0]["content"])["status"] == "ok"
    assert json.loads(tool_messages[0]["content"]) == json.loads(tool_messages[1]["content"])


def test_a_specialist_citation_outside_the_case_is_an_error(routing_server):
    question = "[badcite] Cite something else"
    session_id = send_chat(routing_server, question)["session_id"]
    answer = wait_for_answer(routing_server, session_id, timeout=20)["history"][-1]

    assert "Specialist failed" in answer["content"]
    assert "missing.txt" in answer["content"]
    # The original reply plus one request per citation correction.
    assert len(_question_bodies(NotesSpecialist, question)) == 7


WORKSPACE = APP.parents[1]
CASE_TCGA = WORKSPACE / "data" / "TCGA-DD-A4NF"
NOTES_PYTHON = WORKSPACE / "MedDataOS" / "venv" / "bin" / "python"


class NotesRouter(BaseHTTPRequestHandler):
    """Always consults the notes specialist, then shows that reply."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body["messages"]
        question = next(item["content"] for item in messages if item["role"] == "user")
        tool_msgs = [item for item in messages if item["role"] == "tool"]

        if question == "Fill in the patient card." and not tool_msgs:
            content = json.dumps({
                "name": "TCGA-DD-A4NF",
                "age": "72",
                "sex": "M",
                "blood_type": None,
                "allergies": [],
                "conditions": ["HCC"],
                "data_dates": {},
            })
            payload = FakeAgent.message(content=content)
        elif not tool_msgs:
            payload = FakeAgent.message(tool_calls=[{
                "id": "call_notes",
                "type": "function",
                "function": {
                    "name": "consult_notes",
                    "arguments": json.dumps({"question": question}),
                },
            }])
        else:
            result = json.loads(tool_msgs[-1]["content"])
            text = result.get("result") if result.get("status") == "ok" else (
                "Specialist failed: " + result.get("message", "")
            )
            payload = FakeAgent.message(content=text)

        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.mark.skipif(
    os.getenv("NOTES_LIVE_EVAL") != "1",
    reason="live notes agent: set NOTES_LIVE_EVAL=1",
)
def test_notes_agent_answers_a_real_case(tmp_path):
    """Router calls the real notes specialist on TCGA-DD-A4NF."""
    question = "What was the histology and grade of the resected liver tumor?"
    notes_port = _free_port()
    notes_log = tmp_path / "notes.log"
    log_handle = notes_log.open("w")
    notes_root = str(WORKSPACE / "MedDataOS")
    env = os.environ.copy()
    env.pop("PYTHONSAFEPATH", None)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [notes_root, str(WORKSPACE / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    notes_proc = subprocess.Popen(
        [
            str(NOTES_PYTHON if NOTES_PYTHON.exists() else Path(sys.executable)),
            "-m",
            "src.agents.notes.serve",
            "--case",
            str(CASE_TCGA),
            "--port",
            str(notes_port),
        ],
        cwd=notes_root,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    router = ThreadingHTTPServer(("127.0.0.1", 0), NotesRouter)
    threading.Thread(target=router.serve_forever, daemon=True).start()
    config = tmp_path / "agents.toml"
    config.write_text(
        "\n".join([
            "[notes]",
            f'url = "http://127.0.0.1:{notes_port}/v1"',
            'description = "Answers from clinical notes with verified quotes."',
            "",
        ])
    )

    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            if notes_proc.poll() is not None:
                raise AssertionError(notes_log.read_text()[-2000:])
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{notes_port}/v1/chat/completions", timeout=1)
            except urllib.error.HTTPError:
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise AssertionError("notes agent did not start:\n" + notes_log.read_text()[-2000:])

        with running_server(
            CASE_TCGA,
            agent_url=f"http://127.0.0.1:{router.server_address[1]}/v1",
            agents_file=str(config),
            AGENT_MODEL="router",
            AGENT_TIMEOUT="300",
        ) as server:
            session_id = send_chat(server, question, patient_id="TCGA-DD-A4NF")["session_id"]
            answer = wait_for_answer(server, session_id, timeout=300)["history"][-1]["content"]

        parsed = json.loads(answer)
        text = parsed["response"].lower()
        assert "hepatocellular" in text or "hcc" in text
        assert any(token in text for token in ("moderately", "g2", "grade 2"))
        assert parsed["citations"]
        assert parsed["citations"][0]["web_path"].startswith("/case/")
    finally:
        router.shutdown()
        notes_proc.terminate()
        notes_proc.wait(timeout=20)
        log_handle.close()


def _write_tiny_ct(path: Path, series_uid: str, instance_number: int) -> None:
    import numpy as np
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.PatientID = "TEST"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = series_uid
    ds.Modality = "CT"
    ds.SeriesDescription = "TinyTest"
    ds.InstanceNumber = instance_number
    ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
    ds.ImagePositionPatient = [0.0, 0.0, float(-instance_number)]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 2.0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 8
    ds.Columns = 8
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = np.arange(64, dtype=np.uint16).tobytes()
    ds.save_as(path, enforce_file_format=True)


class DicomFetchAgent(BaseHTTPRequestHandler):
    """Fetches DICOM metadata, then one slice, then cites that series."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body["messages"]
        question = next(item["content"] for item in messages if item["role"] == "user")
        system = messages[0]["content"]
        resources = json.loads(system.split("Case resources: ", 1)[1].split("\n", 1)[0])
        series = next(item for item in resources if item["modality"] == "dicom")
        tool_msgs = [item for item in messages if item["role"] == "tool"]

        if question == "Fill in the patient card.":
            content = json.dumps({
                "name": "Tiny",
                "age": "1",
                "sex": "",
                "blood_type": None,
                "allergies": [],
                "conditions": [],
                "data_dates": {},
            })
        elif len(tool_msgs) == 0:
            payload = FakeAgent.message(tool_calls=[{
                "id": "call_meta",
                "type": "function",
                "function": {
                    "name": "fetch",
                    "arguments": json.dumps({"resource_id": series["id"], "view": "metadata"}),
                },
            }])
            self._send(payload)
            return
        elif len(tool_msgs) == 1:
            payload = FakeAgent.message(tool_calls=[{
                "id": "call_preview",
                "type": "function",
                "function": {
                    "name": "fetch",
                    "arguments": json.dumps({
                        "resource_id": series["id"],
                        "view": "preview",
                        "slice_index": 0,
                        "window": "lung",
                    }),
                },
            }])
            self._send(payload)
            return
        else:
            handle = _cite_handle(tool_msgs)
            content = json.dumps({
                "response": f"The series is a chest CT [cite:{handle}].",
                "citations": [{
                    "cite": handle,
                    "summary": "Lung window, first slice.",
                }],
            })

        self._send(FakeAgent.message(content=content))

    def _send(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def test_a_dicom_citation_keeps_the_fetch(tmp_path):
    pytest.importorskip("pydicom")
    from pydicom.uid import generate_uid

    series = tmp_path / "ct"
    series.mkdir()
    _write_tiny_ct(series / "img.dcm", generate_uid(), 1)
    agent = ThreadingHTTPServer(("127.0.0.1", 0), DicomFetchAgent)
    threading.Thread(target=agent.serve_forever, daemon=True).start()

    try:
        with running_server(
            tmp_path,
            agent_url=f"http://127.0.0.1:{agent.server_address[1]}/v1",
            AGENT_MODEL="dicom",
        ) as server:
            session_id = send_chat(server, "What is the scan?", patient_id=tmp_path.name)["session_id"]
            answer = json.loads(wait_for_answer(server, session_id)["history"][-1]["content"])
            citation = answer["citations"][0]
            preview = citation["dicom"]["previews"][-1]
            assert citation["cite"] == "c2"
            assert citation["id"] == "c2"
            assert citation["command"]["tool"] == "fetch"
            assert citation["command"]["arguments"]["view"] == "preview"
            assert citation["command"]["arguments"]["slice_index"] == 0
            assert citation["command"]["arguments"]["window"] == "lung"
            assert preview["slice_index"] == 0
            assert preview["window"] == "lung"
            assert "metadata" not in citation["dicom"]
            quoted = urllib.parse.urlencode({
                "web_path": citation["web_path"],
                "slice_index": preview["slice_index"],
                "window": preview["window"],
            })
            with urllib.request.urlopen(server["http"] + "/api/dicom/preview?" + quoted) as response:
                body = response.read()
                assert response.headers.get_content_type() == "image/png"
            assert body.startswith(b"\x89PNG\r\n\x1a\n")
    finally:
        agent.shutdown()


def test_a_cite_handle_expands_to_the_call_that_made_it():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import Answer, case as open_case

    calls = {
        "c1": {
            "tool": "fetch",
            "arguments": {"resource_id": "dicom:rt", "view": "metadata"},
            "file": "rt",
            "web_path": "/case/rt",
            "dicom": {"metadata": {"Modality": "RTSTRUCT", "roi_names": ["GTVp"]}},
        },
        "c2": {
            "tool": "fetch",
            "arguments": {
                "resource_id": "dicom:ct",
                "view": "preview",
                "slice_index": 77,
                "overlay": True,
            },
            "file": "ct",
            "web_path": "/case/ct",
            "dicom": {
                "previews": [{
                    "web_path": "/case/ct",
                    "slice_index": 77,
                    "n_slices": 120,
                    "overlay": True,
                }],
            },
        },
        "c3": {
            "tool": "fetch",
            "arguments": {"resource_id": "note:completion", "view": "text"},
            "file": "2006-02-13-rt-completion.txt",
            "web_path": "/case/2006-02-13-rt-completion.txt",
        },
    }
    text = json.dumps({
        "response": (
            "The tumour is contoured on the CT [cite:c2]. "
            "The RTSTRUCT names that contour [cite:c1]. "
            "Treatment finished in February [cite:c3]."
        ),
        "citations": [
            {"cite": "c2", "summary": "Slice 77 with the contour."},
            {"cite": "c1", "summary": "RTSTRUCT metadata."},
            {"cite": "c3", "summary": "Treatment finished."},
        ],
    })

    parsed = json.loads(open_case.expand_citations(text, calls))
    preview_citation = parsed["citations"][0]
    preview = preview_citation["dicom"]["previews"][0]
    assert preview_citation["id"] == "c2"
    assert preview_citation["file"] == "ct"
    assert preview_citation["web_path"] == "/case/ct"
    assert preview_citation["command"]["arguments"]["slice_index"] == 77
    assert preview["slice_index"] == 77
    assert preview["overlay"] is True
    assert "metadata" not in preview_citation["dicom"]
    assert parsed["citations"][1]["dicom"]["metadata"]["Modality"] == "RTSTRUCT"
    assert "dicom" not in parsed["citations"][2]
    assert parsed["citations"][2]["web_path"].endswith("rt-completion.txt")
    assert Answer(text, [], [], calls).problem is None
    adjacent = text.replace(
        "The RTSTRUCT names that contour [cite:c1].",
        "[cite:c2] [cite:c1]",
    )
    assert Answer(adjacent, [], [], calls).problem


def test_every_answer_schema_example_is_valid():
    sys.path.insert(0, str(APP / "web" / "backend"))
    import answer

    for model in (
        answer.Evidence,
        answer.Conflict,
        answer.ImagingCitation,
        answer.NoteCitation,
        answer.TableCitation,
        answer.FileCitation,
        answer.CitedAnswer,
    ):
        for example in model.model_config["json_schema_extra"]["examples"]:
            model.model_validate(example)

    assert json.loads(answer.prompt_schema())["examples"][0] == answer.EXAMPLE


def test_the_strict_answer_schema_uses_only_what_strict_mode_accepts():
    sys.path.insert(0, str(APP / "web" / "backend"))
    import answer

    schema = answer.response_format()["json_schema"]["schema"]
    rejected = {"oneOf", "const", "examples", "default", "title", "discriminator", "minItems"}

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if not isinstance(node, dict):
            return

        assert not rejected & set(node)

        if node.get("type") == "object" and "properties" in node:
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])

        for key, value in node.items():
            walk(list(value.values()) if key in ("properties", "$defs") else value)

    walk(schema)
    assert set(schema["$defs"]) >= {"ImagingCitation", "NoteCitation", "TableCitation"}


def test_a_dicom_call_must_be_cited_as_imaging():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import Answer

    calls = {
        "c1": {
            "tool": "fetch",
            "arguments": {"resource_id": "dicom:ct", "view": "preview", "slice_index": 77},
            "modality": "dicom",
            "file": "ct",
            "web_path": "/case/ct",
        },
    }

    def problem(citation: dict) -> str | None:
        text = json.dumps({
            "response": "The tumour sits at the glottic larynx [cite:c1].",
            "citations": [{"cite": "c1", "summary": "Slice 77.", **citation}],
        })
        return Answer(text, [], [], calls).problem

    assert problem({}) is None
    assert problem({"kind": "imaging", "fields": ["SliceThickness"]}) is None
    assert problem({"kind": "imaging", "web_path": "/case/ct"}) is None

    as_note = problem({"kind": "note"})
    assert "kind 'note'" in as_note and "'imaging'" in as_note

    with_evidence = problem({"evidence": [{"claim": "Tumour", "quote": "glottic"}]})
    assert "evidence is not allowed" in with_evidence
    assert "that note's own fetch" in with_evidence


def test_a_span_fetch_is_attached_to_the_citation():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import case as open_case

    span = open_case._call_span(
        {"modality": "note", "meta": {"note_date": "2005-12-15"}},
        "fetch",
        {"view": "span", "start": 0, "end": 20},
        {
            "view": "span",
            "data": {
                "text": "Consultation for radiotherapy.",
                "start": 0,
                "end": 31,
                "section": "History",
            },
        },
    )
    calls = {
        "c1": {
            "tool": "fetch",
            "arguments": {"resource_id": "note:consult", "view": "span", "start": 0, "end": 31},
            "file": "consult.txt",
            "web_path": "/case/consult.txt",
            "modality": "note",
            "patient_id": "RADCURE-0006",
            "span": span,
        },
    }
    quote_text = "Consultation for radiotherapy."
    text = json.dumps({
        "response": "Consultation for radiotherapy occurred on 2005-12-15 [cite:c1].",
        "citations": [{
            "cite": "c1",
            "summary": "Radiotherapy consult.",
            "evidence": [{
                "n": 1,
                "claim": "Consultation for radiotherapy occurred on 2005-12-15",
                "quote": quote_text,
                "start": 4,
                "end": 9,
            }],
        }],
    })
    from case import Answer
    assert Answer(text, [], [], calls).problem is None
    missing_quote = json.loads(text)
    missing_quote["citations"][0]["evidence"][0].pop("quote")
    assert "quote" in (Answer(json.dumps(missing_quote), [], [], calls).problem or "")

    citation = json.loads(open_case.expand_citations(text, calls))["citations"][0]
    quote = citation["evidence"][0]
    assert citation["agent"] == "clinical_notes"
    assert quote["quote"] == "Consultation for radiotherapy."
    assert quote["start"] == 0
    assert quote["end"] == 30
    assert quote["note_date"] == "2005-12-15"
    assert quote["section"] == "History"
    assert quote["span_url"] == (
        "/api/cases/RADCURE-0006/notes/span?id=note%3Aconsult&start=0&end=30"
    )


def test_a_note_citation_must_quote_an_exact_slice():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import Answer, case as open_case

    note = (
        "Patient ID: RADCURE-0006\n"
        "Date: 2005-12-15\n"
        "Note Type: Radiation Oncology Consultation\n\n"
        "Reason for Consultation:\n"
        "Assessment for radiotherapy for early glottic laryngeal cancer.\n\n"
        "History of Present Illness:\n"
        "This is an 87-year-old male referred for management of biopsy-proven disease. "
        "He reports several months of progressive hoarseness.\n\n"
        "Plan:\n"
        "Given early-stage glottic disease, recommend definitive radiation therapy alone. "
        "No concurrent chemotherapy is indicated.\n"
    )
    stored = open_case._call_span(
        {"modality": "note", "meta": {"note_date": "2005-12-15"}},
        "fetch",
        {"view": "text"},
        {"view": "text", "data": {"text": note}},
    )
    assert stored["origin"] == 0
    assert stored["text"] == note
    calls = {
        "c1": {
            "tool": "fetch",
            "arguments": {"resource_id": "note:consult", "view": "text"},
            "file": "consult.txt",
            "web_path": "/case/consult.txt",
            "modality": "note",
            "patient_id": "RADCURE-0006",
            "span": stored,
        },
    }
    quote = "Given early-stage glottic disease, recommend definitive radiation therapy alone."
    start = note.find(quote)
    cited = {
        "response": "Definitive radiation alone was recommended [cite:c1].",
        "citations": [{
            "cite": "c1",
            "summary": "Definitive radiation alone was recommended.",
            "evidence": [{
                "n": 1,
                "claim": "Definitive radiation alone was recommended.",
                "quote": quote,
                "start": 1,
                "end": 4,
            }],
        }],
    }
    text = json.dumps(cited)
    assert Answer(text, [], [], calls).problem is None
    citation = json.loads(open_case.expand_citations(text, calls))["citations"][0]
    assert citation["evidence"][0]["quote"] == quote
    assert citation["evidence"][0]["start"] == start
    assert "Patient ID" not in citation["evidence"][0]["quote"]
    assert citation["evidence"][0]["span_url"] == (
        f"/api/cases/RADCURE-0006/notes/span?id=note%3Aconsult&start={start}&end={start + len(quote)}"
    )

    absent = json.loads(text)
    absent["citations"][0]["evidence"][0]["quote"] = "chemotherapy was started yesterday"
    assert "not in the text" in (Answer(json.dumps(absent), [], [], calls).problem or "")

    missing = json.loads(text)
    missing["citations"][0].pop("evidence")
    assert "evidence" in (Answer(json.dumps(missing), [], [], calls).problem or "")

    whole = json.loads(text)
    whole["citations"][0]["evidence"] = [{
        "n": 1,
        "claim": "The consult.",
        "quote": note,
        "start": 0,
        "end": len(note),
    }]
    assert "whole note" in (Answer(json.dumps(whole), [], [], calls).problem or "")


def test_a_note_citation_keeps_quotes_and_gains_span_links():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import Answer, case as open_case

    calls = {
        "c1": {
            "tool": "fetch",
            "arguments": {"resource_id": "note:completion", "view": "span", "start": 120, "end": 152},
            "file": "rt-completion.txt",
            "web_path": "/case/rt-completion.txt",
            "modality": "note",
            "patient_id": "RADCURE-0006",
        },
    }
    text = json.dumps({
        "response": "Treatment finished on February 13 [cite:c1].",
        "citations": [{
            "cite": "c1",
            "summary": "The completion note records the last treatment date.",
            "evidence": [{
                "n": 1,
                "claim": "Treatment finished on February 13",
                "quote": "Treatment completed February 13",
                "start": 120,
                "end": 152,
            }],
            "conflicts": [{
                "attribute": "rt.end_date",
                "severity": "high",
                "rationale": "Two notes give different end dates.",
                "values": [
                    {"value": "February 13", "note_label": "rt-completion", "start": 120, "end": 152},
                    {
                        "value": "February 20",
                        "note_label": "follow-up",
                        "note_id": "note:followup",
                        "span_url": "/api/cases/RADCURE-0006/notes/span?id=note:followup&start=40&end=51",
                        "start": 40,
                        "end": 51,
                    },
                ],
            }],
        }],
    })

    parsed = json.loads(open_case.expand_citations(text, calls))
    citation = parsed["citations"][0]
    quote = citation["evidence"][0]
    assert citation["agent"] == "clinical_notes"
    assert citation["id"] == "c1"
    assert quote["note_id"] == "note:completion"
    assert quote["label"] == "rt-completion.txt"
    assert quote["span_url"] == (
        "/api/cases/RADCURE-0006/notes/span?id=note%3Acompletion&start=120&end=152"
    )
    assert citation["conflicts"][0]["values"][0]["span_url"].endswith("start=120&end=152")
    assert citation["conflicts"][0]["values"][1]["span_url"].endswith("start=40&end=51")
    assert Answer(text, [], [], calls).problem is None

    missing_quote = json.loads(text)
    missing_quote["citations"][0]["evidence"][0].pop("quote")
    assert Answer(json.dumps(missing_quote), [], [], calls).problem is None

    bad_offsets = json.loads(text)
    bad_offsets["citations"][0]["evidence"][0]["end"] = 120
    assert Answer(json.dumps(bad_offsets), [], [], calls).problem

    missing = json.dumps({
        "response": "The tumour is contoured [cite:c9].",
        "citations": [{"cite": "c9", "summary": "Missing."}],
    })
    assert Answer(missing, [], [], calls).problem


def test_describing_a_dicom_series_keeps_its_metadata():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import case as open_case

    record = open_case._call_dicom(
        {"modality": "dicom", "web_path": "/case/ct"},
        "describe",
        {},
        {"summary": {"Modality": "CT", "SeriesDescription": "Neck 2.0 CE", "roi_names": []}},
    )

    assert record["metadata"]["Modality"] == "CT"
    assert record["metadata"]["SeriesDescription"] == "Neck 2.0 CE"
    assert "roi_names" not in record["metadata"]


def test_a_fetched_file_must_be_cited_by_its_handle():
    sys.path.insert(0, str(APP / "web" / "backend"))
    from case import Answer

    calls = {
        "c1": {
            "tool": "fetch",
            "arguments": {"resource_id": "note:1", "view": "text"},
            "file": "clinic_note.txt",
            "web_path": "/case/clinic_note.txt",
        },
    }
    opened = [{
        "web_path": "/case/clinic_note.txt",
        "id": "note:1",
        "modality": "note",
        "label": "clinic_note.txt",
    }]
    by_path = json.dumps({
        "response": "The note records fatigue [cite:1].",
        "citations": [{
            "id": "1",
            "file": "clinic_note.txt",
            "web_path": "/case/clinic_note.txt",
            "summary": "Fatigue.",
        }],
    })
    by_handle = json.dumps({
        "response": "The note records fatigue [cite:c1].",
        "citations": [{"cite": "c1", "summary": "Fatigue."}],
    })

    assert Answer(by_path, opened, [], calls).problem
    assert Answer(by_handle, opened, [], calls).problem is None


def test_a_cited_dicom_preview_is_a_png(tmp_path):
    pytest.importorskip("pydicom")
    from pydicom.uid import generate_uid

    series = tmp_path / "ct"
    series.mkdir()
    series_uid = generate_uid()
    _write_tiny_ct(series / "img.dcm", series_uid, 1)
    (tmp_path / "note.txt").write_text("synthetic case")

    with running_server(tmp_path) as server:
        paths = get(server, "/api/dicom/previews")
        assert len(paths) == 1
        assert paths[0].startswith("/case/")
        quoted = urllib.parse.quote(paths[0], safe="")
        with urllib.request.urlopen(server["http"] + "/api/dicom/preview?web_path=" + quoted) as response:
            body = response.read()
            assert response.headers.get_content_type() == "image/png"
        assert body.startswith(b"\x89PNG\r\n\x1a\n")
