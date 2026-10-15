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
def running_server(case_folder, agent_url="http://127.0.0.1:9/v1", **settings):
    port = _free_port()
    env = {key: value for key, value in os.environ.items() if key != "AGENT_URL"}
    env.update(HOST="127.0.0.1", PORT=str(port), **settings)
    process = subprocess.Popen(
        [
            sys.executable,
            str(APP / "web" / "backend" / "server.py"),
            str(case_folder),
            "--agent-url",
            agent_url,
        ],
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

        if "[clump]" in question and has_read and not corrected:
            clumped = json.dumps({
                "response": "The note records fatigue [cite:1][cite:1].",
                "citations": [{
                    "id": "1",
                    "file": "clinic_note.txt",
                    "web_path": note["web_path"],
                    "summary": "Chief complaint: fatigue.",
                }],
            })
            return 200, self.message(content=clumped)

        if "[multi]" in question and has_read:
            return 200, self.message(content=json.dumps({
                "response": "Fatigue began in May [cite:1], and labs were normal [cite:1].",
                "citations": [{
                    "id": "1",
                    "file": "clinic_note.txt",
                    "web_path": note["web_path"],
                    "summary": "Chief complaint: fatigue.",
                }],
            }))

        if "[discover]" in question and has_read:
            return 200, self.message(content="Discovered.")

        if has_read:
            return 200, self.message(content=f"```json\n{cited_note(note['web_path'])}\n```")

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


def test_server_rejects_clumped_citations(dispatch_server):
    question = "[read][clump] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert answer["response"].count("[cite:1]") == 1
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

    assert "[cite:1]" in answer["response"]
    assert answer["citations"][0]["web_path"].endswith("clinic_note.txt")


def test_a_sentence_may_cite_several_files(dispatch_server):
    question = "[read][multi] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert answer["response"] == "Fatigue began in May [cite:1], and labs were normal [cite:1]."
    assert not any(
        item["role"] == "user" and item["content"].startswith("The server refused")
        for item in requests_for(question)[-1]["messages"]
    )


def test_server_asks_the_agent_to_fix_missing_citations(dispatch_server):
    question = "[read][forget] What does the note say?"
    session_id = send_chat(dispatch_server, question)["session_id"]
    answer = json.loads(wait_for_answer(dispatch_server, session_id)["history"][-1]["content"])

    assert "[cite:1]" in answer["response"]
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
