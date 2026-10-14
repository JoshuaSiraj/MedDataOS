"""Example outside agent for MedDataOS.

Connects to the server, waits for questions, and answers them with the
datactrl tools the server exposes.

An OpenAI-compatible model chooses the tools. OPENAI_MODEL is required.
OPENAI_BASE_URL and OPENAI_API_KEY point it at the model server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import urllib.request

from dotenv import load_dotenv

import websockets

load_dotenv()

MAX_STEPS = 8

SYSTEM = (
    "You answer questions about one patient's medical files. "
    "Use the tools to read the files before answering. "
    "Only state what the files say. "
    "The server sends a citation rule with the tools and again with every question. "
    "Follow it. After describe or fetch, the final message is that JSON and nothing else. "
    "Put each [cite:id] inline, immediately after the sentence that file supports. "
    "Do not collect the markers at the end. "
    "If you open no files, reply in plain text."
)


class Agent:
    def __init__(self, sock) -> None:
        self.sock = sock
        self.tools: list[dict] = []
        self.citation: dict = {}
        self.queued: list[dict] = []
        self.session_id: str | None = None

    async def next_message(self) -> dict:
        if self.queued:
            return self.queued.pop(0)

        return json.loads(await self.sock.recv())

    async def call(self, name: str, arguments: dict) -> dict:
        """Run one datactrl tool through the server."""
        await self.sock.send(json.dumps({
            "type": "tool",
            "name": name,
            "arguments": arguments,
            "session_id": self.session_id,
        }))

        while True:
            message = json.loads(await self.sock.recv())

            if message.get("type") == "tool_result":
                return message

            self.queued.append(message)

    async def reply(self, session_id: str, message: str) -> dict:
        """Send a reply and return the server's ok or error."""
        await self.sock.send(json.dumps({
            "type": "reply",
            "session_id": session_id,
            "message": message,
        }))

        while True:
            incoming = json.loads(await self.sock.recv())

            if incoming.get("status") in ("ok", "error") and "type" not in incoming:
                return incoming

            self.queued.append(incoming)


def message_text(text: str) -> str:
    """Drop a markdown fence if the model wrapped the JSON in one."""
    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[-1]

        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()

    return text


def model_instructions(query: dict, agent: Agent) -> str:
    contract = query.get("citation") or agent.citation
    resources = json.dumps(query["case"]["resources"])
    return f"{SYSTEM}\nCitation rule: {json.dumps(contract)}\nCase resources: {resources}"


async def answer_with_model(agent: Agent, query: dict) -> str:
    messages = [{"role": "system", "content": model_instructions(query, agent)}]
    messages += [
        {"role": turn["role"], "content": turn["content"]}
        for turn in query["history"]
    ]

    for _ in range(MAX_STEPS):
        message = await asyncio.to_thread(chat_completion, messages, agent.tools)
        messages.append(message)

        calls = message.get("tool_calls") or []

        if not calls:
            return message_text(message.get("content") or "")

        for call in calls:
            function = call["function"]

            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}

            result = await agent.call(function["name"], arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result),
            })

    return "I could not finish within the step limit."


def revise(previous: str, error: str, query: dict, agent: Agent) -> str:
    """Ask the model to resend a reply the server refused."""
    messages = [
        {"role": "system", "content": model_instructions(query, agent)},
        {"role": "user", "content": query["message"]},
        {"role": "assistant", "content": previous},
        {
            "role": "user",
            "content": (
                "The server refused that reply, or the citations are not inline. "
                "Send only a corrected message. Put each [cite:id] immediately after "
                "the sentence that file supports. Do not group markers at the end. "
                f"Server error: {error}"
            ),
        },
    ]
    return chat_completion(messages, [])["content"] or previous


def chat_completion(messages: list[dict], tools: list[dict]) -> dict:
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}

    if os.getenv("OPENAI_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"

    body = {
        "model": os.environ["OPENAI_MODEL"],
        "messages": messages,
    }

    if tools:
        body["tools"] = tools
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)["choices"][0]["message"]


async def run(url: str) -> None:
    async with websockets.connect(url) as sock:
        agent = Agent(sock)
        print(f"Connected to {url}", flush=True)

        while True:
            message = await agent.next_message()
            kind = message.get("type")

            if kind == "tools":
                agent.tools = message["tools"]
                agent.citation = message.get("citation") or {}
                continue

            if kind != "query":
                continue

            print(f"question: {message['message']}", flush=True)
            session_id = message["session_id"]
            agent.session_id = session_id

            try:
                text = await answer_with_model(agent, message)
            except Exception as exc:
                text = f"The agent failed: {exc}"

            for _ in range(3):
                result = await agent.reply(session_id, text)

                if result.get("status") == "ok":
                    print("reply accepted", flush=True)
                    break

                print(f"reply refused: {result.get('message', '')}", flush=True)

                text = message_text(await asyncio.to_thread(
                    revise,
                    text,
                    result.get("message", ""),
                    message,
                    agent,
                ))

            agent.session_id = None


def main() -> None:
    if not os.getenv("OPENAI_MODEL"):
        raise SystemExit("Set OPENAI_MODEL. This agent only answers with a model.")

    parser = argparse.ArgumentParser(description="Example MedDataOS agent")
    parser.add_argument("--url", default="ws://127.0.0.1:8080/ws/agent")
    args = parser.parse_args()
    asyncio.run(run(args.url))


if __name__ == "__main__":
    main()
