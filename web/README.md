# MedDataOS Web UI

The FastAPI backend opens one local case folder and serves the vanilla
JavaScript UI. Each question goes to the OpenAI-compatible endpoint
passed as `--agent-url`, which reads the case with the server's
`med-datactrl` tools.

From the project root:

```bash
pixi run agent
pixi run serve /path/to/case --agent-url http://127.0.0.1:8001/v1
```

Then open the URL printed by the server. The default bind address is
`127.0.0.1`; set `HOST` and `PORT` in `.env` to override it.

See the project [README](../README.md) for how a question is answered,
and [Connect an agent](../docs/agents.md) for the endpoint the server calls.
