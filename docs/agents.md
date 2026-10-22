# Connect an agent

An agent is an OpenAI-compatible chat completions endpoint. Pass its base URL, the part before `/chat/completions`, when you start the server:

```bash
pixi run serve /path/to/folder --agent-url http://127.0.0.1:8001/v1
```

The server will not start without `--agent-url`. It sends each question there, runs any file reads the agent asks for, and checks citations before the page shows the answer.

## What the server sends

`POST {agent-url}/chat/completions` carries:

- a system message with the citation rule and the case file list,
- the chat so far,
- the datactrl tools as `tools`.

`root` and `case_id` are left off the tools. The server fills `root` from the folder it opened.

At startup the server also sends one request that asks the agent to fill in the patient card. The agent replies with a JSON object holding `name`, `age`, `sex`, `blood_type`, `allergies`, `conditions` and `data_dates`. The sidebar shows the folder name until that reply arrives, and keeps showing it if the reply never comes or isn't valid JSON. Fields with the wrong type are dropped.

These `.env` values go on that request:

| Variable | Meaning |
|---|---|
| `AGENT_MODEL` | Sent as `model`. |
| `AGENT_API_KEY` | Sent as a bearer token, if set. |
| `AGENT_TIMEOUT` | Seconds to wait for each response. Default `120`. |

If the response has `tool_calls`, the server runs them on the open case and sends the results back as `tool` messages, up to eight rounds. The patient-card request allows sixteen rounds. When a response has no tool calls, its content is the answer. A markdown code fence around JSON is removed.

If the citations are wrong, the server sends the agent's answer back with the reason and asks for a corrected one. After six corrections, or if the agent errors or times out, the page shows a short failure message instead of waiting.

If the endpoint answers `400` or `422` to a request that includes `tools`, the server retries that request without them. That agent can then only answer from what is already in the message.

## The example agent

`pixi run agent` serves `examples/agent.py` at `http://127.0.0.1:8001/v1`. It forwards each request to `OPENAI_BASE_URL` (OpenAI by default) using `OPENAI_MODEL`, keeps any `tools` on the request, and returns the model's response. `AGENT_MODEL` is not sent to that model.

To serve an agent you built, accept `POST /v1/chat/completions` and return file reads as `tool_calls`. The server runs those reads. [GraphServe](https://pypi.org/project/graphserve/) serves a LangGraph agent this way.

## More than one agent

`--agent-url` stays the router: the only agent that talks to the page. Specialists are other chat endpoints the router can call. Register them in a TOML file:

```toml
[notes]
url = "http://127.0.0.1:8002/v1"
description = "Answers from clinical notes with verified quotes, dates, and conflicts."

[imaging]
url = "http://127.0.0.1:8003/v1"
description = "Interprets DICOM series the case actually contains."
```

```bash
pixi run serve /path/to/folder --agent-url http://127.0.0.1:8001/v1 --agents agents.toml
```

`--specialist notes=http://127.0.0.1:8002/v1` does the same for one agent, and can be repeated. A name is a short lowercase word. The same name cannot be listed twice.

The router is given one extra tool per specialist, `consult_notes`, `consult_imaging`, and so on. The description is the only routing hint. The server runs that call: it posts the question and the datactrl tools to the specialist, and does not give the specialist a `consult_` tool, so agents cannot call each other. Each specialist is called at most once per question; a second call returns the first result. A timeout, an HTTP error, or citations that still fail after six corrections become a tool error. The router can still answer from the specialists that succeeded.

A specialist may answer in plain text, or with the citation JSON below. A `describe` or `fetch` it calls comes back with a `cite` token, and that token is what the citation names. A specialist that reads the case itself, without those tools, cites the file's `web_path` instead. Files it cites count as opened, so the router's own reply has to cite them too. With no specialists registered, none of this is added and the server talks only to `--agent-url`.

## Clinical notes specialist

To try the notes agent on the page, two processes are enough. Use the MedDataOS virtualenv, not the base conda `python` (that environment does not have `imgtools`). From `MedDataOS`:

```bash
./venv/bin/python -m src.agents.notes.serve --case ../data/TCGA-DD-A4NF
```

In another terminal, from `new_frontend/MedDataOS`, point the page straight at that URL:

```bash
~/scratch/med-datactrl/MedDataOS/venv/bin/python web/backend/server.py \
  ~/scratch/med-datactrl/data/TCGA-DD-A4NF \
  --agent-url http://127.0.0.1:8002/v1
```

The third process, `pixi run agent`, is the router. Add it when more than one specialist is running: `--agent-url` is the router, and the notes process is registered beside it:

```toml
[notes]
url = "http://127.0.0.1:8002/v1"
description = "Answers from clinical notes with verified quotes, dates, and conflicts. Use this for questions about the chart, history, labs in notes, and discrepancies between notes."
```

It opens that case itself and returns citation JSON. Each citation is tagged `clinical_notes` and carries the verified quotes and documented discrepancies, which the page shows on the badge, the hover card, and the source viewer. It does not ask the server to read files.

## Azure OpenAI

The example router and the notes agent both speak Azure when these are set in the `.env` next to that program (`new_frontend/MedDataOS/.env` for the router, `MedDataOS/.env` for the notes agent):

```bash
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-10-21
```

`AZURE_OPENAI_DEPLOYMENT` is the deployment name. `AZURE_OPENAI_API_VERSION` is the date Azure puts on the request. When the key, endpoint, and deployment are set, those calls do not use Gemini. When they are empty, the notes agent keeps using `GEMINI_API_KEY`.

## Citations

Plain text is fine when the agent has not called `describe` or `fetch`. After either of those, the answer must be a JSON string:

```json
{
  "response": "The planning CT and the contours show the larynx [cite:c1] [cite:c2].",
  "citations": [
    {"cite": "c1", "summary": "CT slice."},
    {"cite": "c2", "summary": "RTSTRUCT on the same slice."}
  ]
}
```

Put `[cite:token]` right after the words that call supports. Several tokens may follow one claim. `cite` is the token on the `describe` or `fetch` result, and the marker uses that same token. The server fills in `id`, `file`, `web_path`, and the command before the page sees the reply. A specialist that did not call those tools cites `web_path` instead, with an `id` such as `1`, and that path must be a file in the open case.
