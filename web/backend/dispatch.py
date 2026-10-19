"""Hold the conversation with the agent at --agent-url for each question.

The agent is any OpenAI-compatible chat completions endpoint: a plain model,
or an agent served behind that API. Tool calls it makes are run here on the
open case, its answer is sent back for correction until the citations pass,
and the accepted answer is pushed to every open page. At startup the agent
also fills in the patient card from the files.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request

from case import Answer, Profile, case
from registry import Specialist
from state import log, short_session, state


_tasks: set[asyncio.Task] = set()


def _background(coroutine) -> None:
    task = asyncio.create_task(coroutine)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


class AgentError(Exception):
    """The agent endpoint failed or returned something that is not a chat completion."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AgentClient:
    """HTTP client for the OpenAI-compatible endpoint at --agent-url."""

    def __init__(self, url: str, model: str, key: str | None, timeout: float) -> None:
        self.url = url
        self.model = model
        self.key = key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> AgentClient:
        return cls(
            state.agent_url or "",
            os.getenv("AGENT_MODEL", ""),
            os.getenv("AGENT_API_KEY"),
            float(os.getenv("AGENT_TIMEOUT", "120")),
        )

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        """One chat completions request. Returns the assistant message."""
        headers = {"Content-Type": "application/json"}

        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"

        body: dict = {"model": self.model, "messages": messages}

        if tools:
            body["tools"] = tools

        request = urllib.request.Request(
            f"{self.url}/chat/completions",
            data=json.dumps(body).encode(),
            headers=headers,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise AgentError(self._http_error(exc), exc.code) from exc
        except urllib.error.URLError as exc:
            raise AgentError(f"could not reach {self.url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise AgentError(f"{self.url} did not return JSON") from exc

        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AgentError(f"{self.url} did not return a chat completion") from exc

        if not isinstance(message, dict):
            raise AgentError(f"{self.url} did not return a chat completion")

        return message

    def _http_error(self, exc: urllib.error.HTTPError) -> str:
        detail = ""

        try:
            body = json.loads(exc.read() or b"{}")
            error = body.get("error") if isinstance(body, dict) else None
            detail = error.get("message", "") if isinstance(error, dict) else str(error or "")
        except (OSError, json.JSONDecodeError):
            pass

        return f"{self.url} answered {exc.code}" + (f": {detail}" if detail else "")


class Conversation:
    """Messages exchanged with the agent for one piece of work, including tool calls."""

    MAX_STEPS = 8

    def __init__(
        self,
        messages: list[dict],
        session_id: str,
        client: AgentClient | None = None,
        tools: list[dict] | None = None,
        consult: bool = False,
    ) -> None:
        self.messages = messages
        self.session_id = session_id
        self.client = client or AgentClient.from_env()
        self.tools = list(case.tools if tools is None else tools)
        self.consult = consult

    async def reply(self) -> str:
        """Call the agent until it stops asking for tools, then return its text."""
        for _ in range(self.MAX_STEPS):
            message = await self._next()
            self.messages.append(message)
            calls = message.get("tool_calls") or []

            if not calls:
                return message.get("content") or ""

            for call in calls:
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(await self._run_call(call)),
                })

        raise AgentError(f"no answer after {self.MAX_STEPS} steps")

    async def _next(self) -> dict:
        try:
            return await asyncio.to_thread(self.client.complete, self.messages, self.tools)
        except AgentError as exc:
            if not self.tools or exc.status not in (400, 422):
                raise

        log("server", "agent refused the tool list, retrying without it")
        self.tools = []
        return await asyncio.to_thread(self.client.complete, self.messages, self.tools)

    async def _run_call(self, call: dict) -> dict:
        function = call.get("function") or {}
        name = function.get("name", "")

        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError as exc:
            return {"status": "error", "name": name, "message": f"Arguments are not valid JSON: {exc}"}

        if not isinstance(arguments, dict):
            return {"status": "error", "name": name, "message": "Arguments must be a JSON object"}

        if name.startswith("consult_"):
            return await self._consult(name, arguments)

        return await asyncio.to_thread(case.run, name, arguments, self.session_id)

    async def _consult(self, name: str, arguments: dict) -> dict:
        """Call one registered specialist. A second call returns the first result."""
        if not self.consult:
            return {
                "status": "error",
                "name": name,
                "message": "This agent cannot call another specialist.",
            }

        specialist_name = name.removeprefix("consult_")
        specialist = state.specialists.get(specialist_name)

        if specialist is None:
            return {"status": "error", "name": name, "message": f"Unknown specialist: {specialist_name}"}

        question = arguments.get("question")

        if not isinstance(question, str) or not question.strip():
            return {"status": "error", "name": name, "message": "question must be a non-empty string"}

        cache = state.consulted.setdefault(self.session_id, {})

        if specialist_name in cache:
            log("agent", f"session={short_session(self.session_id)} consult {specialist_name} already answered")
            return cache[specialist_name]

        result = await consult_specialist(specialist, question.strip(), self.session_id)
        cache[specialist_name] = result
        return result


def router_tools() -> list[dict]:
    """Datactrl tools, plus one consult tool per registered specialist."""
    return [*case.tools, *(spec.tool() for spec in state.specialists.values())]


def _client_for(url: str) -> AgentClient:
    return AgentClient(
        url,
        os.getenv("AGENT_MODEL", ""),
        os.getenv("AGENT_API_KEY"),
        float(os.getenv("AGENT_TIMEOUT", "120")),
    )


_SPECIALIST_RULE = (
    "The reply may be plain text. "
    "To cite files, the whole reply is one JSON object with a \"response\" string "
    "and a \"citations\" list, like the example. "
    "Put each [cite:id] right after the words that file supports. "
    "A sentence may cite several files, but never put markers side by side "
    "or group them at the end of the answer. "
    "Each citation's web_path must be one of the case files."
)


def specialist_instructions() -> str:
    """Prompt for a specialist: cite case files, and do not call other agents."""
    return "\n".join([
        "You are a specialist answering one question about one patient's medical files. "
        "Use the tools to read the files when you need them. "
        "Ground your answer in the files. "
        "Do not call another specialist.",
        f"Citation rule: {_SPECIALIST_RULE}",
        f"Example of a cited reply: {json.dumps(Answer.EXAMPLE)}",
        f"Case resources: {json.dumps(case.files())}",
    ])


def _remember_citations(session_id: str, text: str) -> None:
    """Treat files named in an accepted specialist answer as opened for the router."""
    if session_id not in state.pending:
        return

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return

    citations = parsed.get("citations") if isinstance(parsed, dict) else None

    if not isinstance(citations, list):
        return

    known = {item["web_path"]: item for item in case.files()}
    opened = state.reads.setdefault(session_id, [])
    seen = {item["web_path"] for item in opened}

    for citation in citations:
        if not isinstance(citation, dict):
            continue

        ref = known.get(citation.get("web_path"))

        if ref and ref["web_path"] not in seen:
            opened.append(ref)
            seen.add(ref["web_path"])


async def consult_specialist(specialist: Specialist, question: str, session_id: str) -> dict:
    """Ask one specialist, then return its answer or a tool error. Never raises."""
    label = short_session(session_id)
    name = f"consult_{specialist.name}"
    log("server", f"session={label} consult {specialist.name}: {question}")
    conversation = Conversation(
        [
            {"role": "system", "content": specialist_instructions()},
            {"role": "user", "content": question},
        ],
        session_id,
        client=_client_for(specialist.url),
        tools=list(case.tools),
        consult=False,
    )
    problem = ""

    try:
        for attempt in range(1, Question.MAX_REVISIONS + 2):
            text = message_text(await conversation.reply())

            if not text.strip():
                problem = "The reply was empty."
                verdict = None
            else:
                verdict = Answer(text, [], case.files())
                problem = verdict.problem or ""

            if verdict is not None and verdict.problem is None:
                _remember_citations(session_id, text)
                log("agent", f"session={label} consult {specialist.name} ok")
                return {"status": "ok", "name": name, "result": text}

            log("agent", f"session={label} consult {specialist.name} reply {attempt} refused: {problem}")
            correction = (
                verdict.correction()
                if verdict is not None
                else f"The server refused that answer. {problem}"
            )
            conversation.messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": correction},
            ]
    except Exception as exc:
        log("agent", f"session={label} consult {specialist.name} failed: {exc}")
        return {"status": "error", "name": name, "message": str(exc)}

    return {
        "status": "error",
        "name": name,
        "message": f"The specialist could not produce valid citations. Last problem: {problem}",
    }


class Question:
    """One user question: ask, then send refused answers back until one passes."""

    MAX_REVISIONS = 3
    PROMPT = (
        "You answer questions about one patient's medical files. "
        "Use the tools to read the files before answering. "
        "Ground your answer in the files. "
        "If you open no files, reply to the user in plain text, not JSON. "
        "Otherwise the whole reply is one JSON object that follows the citation rule below, "
        "with no sentences before or after it. "
        "Put each [cite:id] inline, right after the words that file supports. "
        "Do not put markers side by side or collect them at the end. "
        "Use a short citation id such as 1."
    )

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.label = short_session(session_id)

    def start(self) -> None:
        state.pending.add(self.session_id)
        question = state.sessions[self.session_id].history[-1]["content"]
        log("server", f"session={self.label} question sent to the agent: {question}")
        _background(self.answer())

    async def answer(self) -> None:
        history = state.sessions[self.session_id].history
        conversation = Conversation(
            [{"role": "system", "content": self._instructions()}]
            + [{"role": turn["role"], "content": turn["content"]} for turn in history],
            self.session_id,
            tools=router_tools(),
            consult=bool(state.specialists),
        )
        problem = ""

        try:
            for attempt in range(1, self.MAX_REVISIONS + 2):
                text = message_text(await conversation.reply())

                if self.session_id not in state.pending:
                    return

                opened = state.reads.get(self.session_id, [])
                verdict = Answer(text, opened, case.files())
                problem = verdict.problem or ""

                if verdict.problem is None:
                    await self._deliver(text)
                    return

                log("agent", f"session={self.label} reply {attempt}/{self.MAX_REVISIONS + 1} refused: {problem}")
                log("agent", f"session={self.label} refused reply was: {text}")
                conversation.messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": verdict.correction()},
                ]

            await self._deliver(
                "The agent could not produce an answer with valid citations. "
                f"Last problem: {problem}"
            )

        except Exception as exc:
            log("server", f"session={self.label} agent failed: {exc}")
            await self._deliver(f"The agent failed: {exc}")
        finally:
            state.consulted.pop(self.session_id, None)

    def _instructions(self) -> str:
        lines = [
            self.PROMPT,
            f"Citation rule: {Answer.RULE}",
            f"Example of a cited reply: {json.dumps(Answer.EXAMPLE)}",
            f"Case resources: {json.dumps(case.files())}",
        ]

        if state.specialists:
            roster = "; ".join(
                f"consult_{name}: {spec.description}" for name, spec in state.specialists.items()
            )
            lines.append(
                "Specialists: " + roster + ". "
                "Call consult_<name> with the part of the question that specialist answers. "
                "Call each specialist at most once. "
                "When a specialist returns citation JSON, cite those files in your own reply. "
                "If a specialist returns an error, say so and answer from the others."
            )

        return "\n".join(lines)

    async def _deliver(self, message: str) -> None:
        """Record the answer once, stop waiting, and push it to every open page."""
        if self.session_id not in state.pending:
            return

        state.pending.discard(self.session_id)
        state.reads.pop(self.session_id, None)

        session = state.sessions[self.session_id]
        session.add("assistant", message)
        session.processing = False

        await state.hub.assistant(self.session_id, message)
        log(
            "server",
            f"session={self.label} answer sent to "
            f"{len(state.hub.connections)} page(s): {self._preview(message)}",
        )

    @staticmethod
    def _preview(message: str) -> str:
        try:
            parsed = json.loads(message)
        except json.JSONDecodeError:
            return message

        if isinstance(parsed, dict) and isinstance(parsed.get("response"), str):
            citations = parsed.get("citations")
            count = len(citations) if isinstance(citations, list) else 0
            return f"{count} citation(s): {parsed['response']}"

        return message


class PatientCard:
    """The startup request that asks the agent to fill in the sidebar card."""

    PROMPT = (
        "You fill in the patient card for one patient's medical files. "
        "Use the tools to read the files. Do not guess: leave a field empty when the files do not say. "
        "Reply with only one JSON object with these keys: "
        '"name" (string), "age" (string, such as "64"), "sex" (string), '
        '"blood_type" (string, or null), "allergies" (list of strings), '
        '"conditions" (list of strings), and "data_dates" (object mapping each top-level '
        "folder of the case to the latest date in it, as YYYY-MM-DD)."
    )

    async def fill(self) -> None:
        conversation = Conversation(
            [
                {"role": "system", "content": f"{self.PROMPT}\nCase resources: {json.dumps(case.files())}"},
                {"role": "user", "content": "Fill in the patient card."},
            ],
            "",
        )

        try:
            profile = Profile.from_agent(json.loads(_strip_fence(await conversation.reply())))
        except Exception as exc:
            log("server", f"patient card not filled, showing the folder name: {exc}")
            return

        state.profile = profile.as_dict()
        filled = {key: value for key, value in state.profile.items() if value}
        log("server", f"patient card filled: {json.dumps(filled) if filled else 'nothing found in the files'}")

        card = case.patient()

        if card:
            await state.hub.broadcast({"type": "patient", "patient": card.as_dict()})


def ask(session_id: str) -> None:
    """Answer the latest question in this session in the background."""
    Question(session_id).start()


def fill_card() -> None:
    """Ask the agent for the patient card in the background, then push it to the pages."""
    log("server", "asking the agent to fill in the patient card")
    _background(PatientCard().fill())


def _strip_fence(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[-1]

        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()

    return text


def message_text(text: str) -> str:
    """Drop a markdown fence, and a JSON wrapper when the answer has no citations."""
    text = _strip_fence(text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text

    if not isinstance(parsed, dict) or parsed.get("citations"):
        return text

    for key in ("message", "response", "text"):
        value = parsed.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return text
