"""One-line traces for the page, the server, and outside agents."""

from __future__ import annotations


def log(who: str, message: str) -> None:
    text = " ".join(message.split())

    if len(text) > 180:
        text = text[:177] + "..."

    print(f"{who:<6} {text}", flush=True)


def session(session_id: str) -> str:
    return session_id[:8] if session_id else "?"
