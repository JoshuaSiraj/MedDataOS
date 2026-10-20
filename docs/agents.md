# Connect an agent

An agent is an HTTP server that accepts `POST {base}/chat/completions` and returns an OpenAI chat completion. Pass `base`, the part before `/chat/completions`, when you start MedDataOS:

```bash
pixi run serve /path/to/folder --agent-url http://127.0.0.1:8001/v1
```

The server will not start without `--agent-url`. For each question it sends the chat, runs any tool calls on the open folder, and checks the answer before the page shows it.

## What the server sends

Each request is JSON:

| Field | Value |
|---|---|
| `model` | `AGENT_MODEL` from `.env`. Empty when that variable is unset. |
| `messages` | The system message, then the session history. |
| `tools` | The med-datactrl tools, omitted on the retry described below. |

`AGENT_API_KEY`, when set, is sent as `Authorization: Bearer …`. `AGENT_TIMEOUT` is how many seconds the server waits for each response. The default is `120`.

The system message for a question contains:

- instructions to read the files with the tools and to ground the answer in them,
- the citation rule and a JSON example,
- `Case resources:` followed by a JSON list of discovered files.

Each resource in that list has `id`, `modality` (`note`, `structured`, or `dicom`), `label`, and `web_path`. `web_path` is the file's URL on this server, such as `/case/clinic_note.txt`. Paths are URL-encoded per segment. The list is the `resources` array from the discovery report.

The tools are `discover`, `describe`, `fetch`, `links`, `assert_link`, `dicom_tree`, and `dicom_groups`. Their schemas come from med-datactrl. `root` and `case_id` are removed from every schema, including `required`. The server drops those two arguments if the agent sends them, and sets `root` to the folder it opened before it runs the tool.

A tool result comes back as a `tool` message whose content is JSON:

```json
{"status": "ok", "name": "fetch", "result": {}}
```

A tool that raises, or arguments that are not a JSON object, come back as `{"status": "error", "name": "…", "message": "…"}` so the agent can try again. The server does not stop the question for that.

The server calls the agent again with those tool messages, up to eight completions. If the eighth completion still contains `tool_calls`, the page shows `The agent failed: no answer after 8 steps`.

If the endpoint answers `400` or `422` to a request that includes `tools`, the server retries that request once without `tools` and does not send tools again for the rest of that question. The agent can then answer only from the messages it has already been given.

When a completion has no `tool_calls`, its `content` is the answer. The server removes one markdown fence: a leading ` ``` ` line and a trailing ` ``` `. If the remaining text is a JSON object whose `citations` field is missing or empty, and `message`, `response`, or `text` is a non-empty string, that string replaces the object. An object that has citations is left as JSON for the check below.

## Patient card

When the server starts, it sends a separate completion. The system message asks for one JSON object and includes the same case resource list. The user message is `Fill in the patient card.`

The object may contain:

| Key | Kept when |
|---|---|
| `name`, `age`, `sex` | A string or number. Numbers are stored as text. |
| `blood_type` | Same. A blank value is stored as empty. |
| `allergies`, `conditions` | A list. Only non-empty strings are kept. |
| `data_dates` | An object whose values are `YYYY-MM-DD`. Other values are dropped. |

A markdown fence around that JSON is removed. Any other shape, invalid JSON, or a failed request leaves the card as the folder name. The sidebar already shows that name, and the server pushes the filled card to open pages when the reply is usable. Notes, Tables, and DICOM on the card come from the discovery report. `data_dates` is shown beside a citation when the cited path is `/case/<folder>/…` and `<folder>` is a key in `data_dates`.

## Citations

`describe` and `fetch` record the resource they were called with, when that id is in the case file list. Those are the opened files. Other tools do not open a file. A failed call does not either.

If no file was opened, the answer is shown when it is plain text and contains neither `[cite:` nor `"citations"`. A JSON object in that case is refused with a request for plain text. Text that does contain a citation marker is checked with the rules below, against every discovered file.

If a file was opened, the whole answer must be one JSON object:

```json
{
  "response": "The planned dose was 51 Gy [cite:1]. Treatment finished on February 13 [cite:2].",
  "citations": [
    {
      "id": "1",
      "file": "note.txt",
      "web_path": "/case/note.txt",
      "summary": "Short excerpt that supports the sentence."
    },
    {
      "id": "2",
      "file": "completion.txt",
      "web_path": "/case/completion.txt",
      "summary": "Short excerpt for the second sentence."
    }
  ]
}
```

That object is the example the server sends in the prompt. The check accepts an answer when all of these hold:

- `response` is a string and `citations` is a list with at least one usable entry.
- `response` contains `[cite:id]` for each usable citation. `id` is a string with no spaces.
- `file` is a non-empty string and `summary` is a string.
- `web_path` is one of the files opened for this question.
- Each marker sits after the words it supports. Two markers with only space or a comma or semicolon between them are refused, and so is a marker that is the only text in a sentence. One sentence may cite more than one file when words separate the markers.

Usable entries are enough. A list may also contain entries the check ignores, as long as one entry passes.

A refused answer is appended to the conversation, followed by a user message that starts with `The server refused that answer.`, states the problem, repeats the rule and the example, and lists the opened `web_path` values. The server does this at most three times after the original answer. The next failure is shown on the page as `The agent could not produce an answer with valid citations. Last problem: …`.

Anything other than a chat completion (`choices[0].message` as an object), a connection error, or a timeout is shown as `The agent failed: …`.

## The example agent

`pixi run agent` runs `examples/agent.py`. It listens on `127.0.0.1:8001` unless you pass `--host` and `--port`, and it accepts only `POST /v1/chat/completions`.

It replaces `model` with `OPENAI_MODEL` and posts `messages`, plus `tools` when the request includes them, to `OPENAI_BASE_URL`. When `OPENAI_BASE_URL` is unset it uses `https://api.openai.com/v1`. `OPENAI_API_KEY` is sent as a bearer token when set. The example agent's own wait is 120 seconds. `AGENT_MODEL`, `AGENT_API_KEY`, and `AGENT_TIMEOUT` apply to the MedDataOS server's call, which this forwarder does not read.

`OPENAI_MODEL` must be set or the example agent exits. Point `--agent-url` at another endpoint when you do not want this forwarder.
