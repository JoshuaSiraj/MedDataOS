"""Example agent served as an OpenAI chat completions endpoint.

Start it, then pass the address it prints as --agent-url when launching the
server. MedDataOS posts each question to /v1/chat/completions. This forwards that request to the model at
OPENAI_BASE_URL and returns the model's message, including any tool calls.
MedDataOS runs those tools.

Set OPENAI_MODEL, or the Azure variables AZURE_OPENAI_API_KEY,
AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, and optionally
AZURE_OPENAI_API_VERSION (a date such as 2024-10-21). OPENAI_API_KEY is
sent when set. Azure uses the api-key header.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

from dotenv import load_dotenv


load_dotenv()


def _target() -> tuple[str, dict, str | None]:
    """Return the chat URL, headers, and model name. Model is None for Azure."""
    key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    if key and endpoint and deployment:
        version = quote(os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"), safe="")
        url = (
            endpoint.rstrip("/")
            + f"/openai/deployments/{quote(deployment, safe='')}/chat/completions"
            + f"?api-version={version}"
        )
        return url, {"Content-Type": "application/json", "api-key": key}, None

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if os.getenv("OPENAI_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"
    return base + "/chat/completions", headers, os.environ["OPENAI_MODEL"]


def forward(body: dict) -> tuple[int, dict]:
    """Send one chat completion to the model and return its status and body."""
    url, headers, model = _target()
    outgoing = {"messages": body.get("messages") or []}

    if model:
        outgoing["model"] = model

    if body.get("tools"):
        outgoing["tools"] = body["tools"]

    request = urllib.request.Request(
        url,
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
    azure = (
        os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("AZURE_OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )
    if not os.getenv("OPENAI_MODEL") and not azure:
        raise SystemExit(
            "Set OPENAI_MODEL, or AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, "
            "and AZURE_OPENAI_DEPLOYMENT."
        )

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
