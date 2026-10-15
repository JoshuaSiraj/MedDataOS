"""Example agent served as an OpenAI chat completions endpoint.

Start it, then pass the address it prints as --agent-url when launching the
server. MedDataOS posts each question to /v1/chat/completions. This forwards that request to the model at
OPENAI_BASE_URL and returns the model's message, including any tool calls.
MedDataOS runs those tools.

OPENAI_MODEL is required. OPENAI_API_KEY is sent when set.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import load_dotenv


load_dotenv()


def forward(body: dict) -> tuple[int, dict]:
    """Send one chat completion to the model and return its status and body."""
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}

    if os.getenv("OPENAI_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"

    outgoing = {
        "model": os.environ["OPENAI_MODEL"],
        "messages": body.get("messages") or [],
    }

    if body.get("tools"):
        outgoing["tools"] = body["tools"]

    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(outgoing).encode(),
        headers=headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {"error": {"message": exc.reason}}
        except json.JSONDecodeError:
            payload = {"error": {"message": raw or exc.reason}}
        return exc.code, payload


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        status, payload = forward(body)
        data = json.dumps(payload).encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        print(f"agent  {args[0]}", flush=True)


def main() -> None:
    if not os.getenv("OPENAI_MODEL"):
        raise SystemExit("Set OPENAI_MODEL. This agent forwards questions to that model.")

    parser = argparse.ArgumentParser(description="Example MedDataOS agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    host, port = server.server_address
    print(f"Agent: http://{host}:{port}/v1", flush=True)
    print(f"Launch the server with --agent-url http://{host}:{port}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
