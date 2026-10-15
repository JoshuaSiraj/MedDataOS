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

If the response has `tool_calls`, the server runs them on the open case and sends the results back as `tool` messages, up to eight rounds. When a response has no tool calls, its content is the answer. A markdown code fence around JSON is removed.

If the citations are wrong, the server sends the agent's answer back with the reason and asks for a corrected one. After three corrections, or if the agent errors or times out, the page shows a short failure message instead of waiting.

If the endpoint answers `400` or `422` to a request that includes `tools`, the server retries that request without them. That agent can then only answer from what is already in the message.

## The example agent

`pixi run agent` serves `examples/agent.py` at `http://127.0.0.1:8001/v1`. It forwards each request to `OPENAI_BASE_URL` (OpenAI by default) using `OPENAI_MODEL`, keeps any `tools` on the request, and returns the model's response. `AGENT_MODEL` is not sent to that model.

To serve an agent you built, accept `POST /v1/chat/completions` and return file reads as `tool_calls`. The server runs those reads. [GraphServe](https://pypi.org/project/graphserve/) serves a LangGraph agent this way.

## Citations

Plain text is fine when the agent has not called `describe` or `fetch`. After either of those, the answer must be a JSON string:

```json
{
  "response": "The note records fatigue [cite:1].",
  "citations": [
    {
      "id": "1",
      "file": "clinic_note.txt",
      "web_path": "/case/clinic_note.txt",
      "summary": "Chief complaint: fatigue."
    }
  ]
}
```

Put each `[cite:id]` immediately after the sentence that file supports, one marker per sentence. `web_path` must be a file opened for this question.
