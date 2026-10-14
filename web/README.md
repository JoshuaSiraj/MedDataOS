# MedDataOS Web UI

The FastAPI backend opens one local case folder and serves the vanilla
JavaScript UI. Outside agents connect over WebSocket, use the server's
`med-datactrl` tools, and return answers to browser sessions.

From the project root:

```bash
pixi run serve /path/to/case
pixi run agent
```

Then open the URL printed by the server. The default bind address is
`127.0.0.1`; set `HOST` and `PORT` to override it.

See the project [README](../README.md) for how a question is answered
and how to run the tests.
