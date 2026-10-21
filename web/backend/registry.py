"""Specialist endpoints the router may call.

A specialist is another OpenAI-compatible chat agent. The page still talks to
one router at --agent-url. Each specialist is offered to that router as a
consult_<name> tool. With no specialists registered, the server behaves as a
single agent.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")


@dataclass(frozen=True)
class Specialist:
    """One named agent the router can consult."""

    name: str
    url: str
    description: str

    def tool(self) -> dict:
        """OpenAI tool the router uses to call this specialist."""
        return {
            "type": "function",
            "function": {
                "name": f"consult_{self.name}",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "What this specialist should answer.",
                        },
                    },
                    "required": ["question"],
                },
            },
        }


def load_specialists(path: str | None, flags: list[str] | None) -> dict[str, Specialist]:
    """Load specialists from an optional TOML file, then from NAME=URL flags.

    Names must be unique across both. The server exits if a name or URL is
    unusable, so a bad registry never comes up half-configured.
    """
    found: dict[str, Specialist] = {}

    if path:
        found.update(_from_toml(Path(path)))

    for flag in flags or []:
        specialist = _from_flag(flag)

        if specialist.name in found:
            raise SystemExit(f"Specialist {specialist.name} is listed more than once")

        found[specialist.name] = specialist

    return found


def _from_toml(path: Path) -> dict[str, Specialist]:
    if not path.is_file():
        raise SystemExit(f"Agents file not found: {path}")

    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SystemExit(f"Could not read {path}: {exc}") from exc

    if not isinstance(data, dict) or not data:
        raise SystemExit(f"No specialists in {path}")

    found: dict[str, Specialist] = {}

    for name, body in data.items():
        if not isinstance(body, dict) or not isinstance(body.get("url"), str):
            raise SystemExit(f"Specialist {name} needs a url")

        description = body.get("description", "")

        if not isinstance(description, str):
            raise SystemExit(f"Specialist {name} description must be a string")

        found[str(name)] = _make(str(name), body["url"], description)

    return found


def _from_flag(flag: str) -> Specialist:
    name, sep, url = flag.strip().partition("=")

    if not sep or not url.strip():
        raise SystemExit(f"Specialist must be name=url, got {flag!r}")

    return _make(name.strip(), url.strip(), "")


def _make(name: str, url: str, description: str) -> Specialist:
    if not _NAME.fullmatch(name):
        raise SystemExit(
            f"Specialist name {name!r} must be a short lowercase word, such as notes"
        )

    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"Specialist {name} url must start with http:// or https://")

    text = description.strip() or f"Consult the {name} specialist."
    return Specialist(name, url.rstrip("/"), text)
