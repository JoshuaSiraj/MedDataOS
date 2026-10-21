# MedDataOS page

The server in `web/backend` opens one case folder and serves this page. Start it from the project root as the [README](../README.md) describes. The page is the URL printed at startup, with `?patient=` set to the folder name. Optional specialists are registered with `--agents` or `--specialist`; see [Connect an agent](../docs/agents.md).

`HOST` and `PORT` in `.env` bind the server. The defaults are `127.0.0.1` and `8080`. When `HOST` is `0.0.0.0` or `::`, the printed URL still uses `127.0.0.1`.

## Sidebar

`GET /api/patients` returns the open folder. Its id and, until the agent answers, its name are the folder name. The startup request in [Connect an agent](../docs/agents.md) can replace the name, age, sex, blood type, allergies, and conditions. Hovering the name shows that card, plus Notes, Tables, or DICOM when the discovery report contains those files.

The folder's files are served at `/case/…`. A citation's `web_path` points there.

Conversations under the patient are the chat sessions for that folder name. `+ New` creates an empty one. The label is the first 60 characters of the first question, or `New conversation`. Sessions live in this process. After a restart the list is empty, and a session id still stored in the browser is not reused.

## Chat

The box posts `message`, and the current `session_id` and `patient_id` when it has them, to `POST /api/chat`. Send stays disabled until the WebSocket is open, the box has text, and the current session is idle. Enter sends; Shift+Enter inserts a line.

The reply arrives on the WebSocket as `type: assistant` for that session. The page also reads `GET /api/session/{id}` on reconnect and every few seconds while it is waiting, so a reply still shows if the socket missed it. A second question in a session that is already waiting returns an error and is not sent to the agent.

An assistant message that is JSON with `response` and a non-empty `citations` list is rendered from `response`. Each `[cite:id]` becomes a Source marker. Hovering it previews the file at `web_path`: png, jpg, jpeg, and svg as an image, mp4 as video, wav as audio, csv as a table, and anything else as text. Opening the marker shows that file and the citation summary. A summary that splits into two or more pieces of at least 20 characters, on a period or a newline, becomes a checkbox list of up to eight boxes. Checked boxes are stored for this process with `PATCH /api/patients/{id}/reviews`, under the citation's web path.

Other assistant text is shown as markdown. `Clear` drops the selection on the page. The session remains on the server.

The paperclip accepts `.csv` and `.xlsx`. The server writes the bytes to `data/input/dataset.csv` or `data/input/dataset.xlsx`, replacing the previous upload, and appends `[Uploaded file: <name>]` to the question. The agent sees that line. The file stays out of the case folder, so the med-datactrl tools do not list it. `data/` is gitignored.

## Pins

The pin control on a citation, or a selection inside an assistant message, posts to `/api/patients/{id}/pins`. A citation pin stores the citation, the question text, and the session id. A text pin stores the selected text and the session id. Pinning the same citation web path, or the same text, again returns the existing pin.

The right-hand panel lists pins for the open patient. Unpinning deletes that pin. A note and the tags `#follow-up`, `#critical`, `#reviewed`, `#discuss`, and `#normal` are saved on a citation pin with `PATCH`. Pins last until the process stops. Choosing a pin scrolls the source session to that citation or text.
