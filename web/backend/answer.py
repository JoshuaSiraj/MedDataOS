"""The answer an agent sends after describe or fetch, as Pydantic models.

The JSON schema of ``CitedAnswer``, with its descriptions and examples, is what the
agent is shown. A strict copy goes out as ``response_format`` so a model that supports
structured outputs replies in this shape. The server still checks what a schema cannot:
that each cite token is a call from this question, that a quote is in the note, and
where the markers sit.
"""

from __future__ import annotations

import json
from functools import cache
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

# ---------------------------------------------------------------------------
# Note evidence
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """One claim from a note, and the passage in that note that supports it."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [
            {
                "n": 1,
                "claim": "Treatment finished on February 13",
                "quote": "Treatment completed February 13",
            },
        ]},
    )

    n: int | None = Field(default=None, description="Claim number, starting at 1.")
    claim: str = Field(description="The words in response that this quote supports.")
    quote: str | None = Field(
        default=None,
        description=(
            "Required for a note read with fetch view=text. "
            "A short contiguous passage copied exactly from the text that fetch returned: "
            "the words that support the claim, not the whole note. "
            "Do not send start or end; the server finds the passage."
        ),
        examples=["Treatment completed February 13", "51 Gy in 20 fractions"],
    )


class ConflictValue(BaseModel):
    """What one note says about the disputed attribute, and where in that note."""

    model_config = ConfigDict(extra="ignore")

    value: str = Field(examples=["February 13"])
    note_label: str | None = Field(default=None, examples=["rt-completion"])
    note_id: str | None = Field(
        default=None,
        description="Resource id of that note, when it is not the note this citation fetched.",
        examples=["note:followup"],
    )
    start: int | None = Field(default=None, description="Character offset in that note.")
    end: int | None = Field(default=None, description="Character offset in that note, after start.")


class Conflict(BaseModel):
    """Two or more notes that disagree about one attribute."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [
            {
                "attribute": "rt.end_date",
                "severity": "high",
                "rationale": "The completion note and the follow-up note give different end dates.",
                "values": [
                    {"value": "February 13", "note_label": "rt-completion", "start": 120, "end": 151},
                    {
                        "value": "February 20",
                        "note_label": "follow-up",
                        "note_id": "note:followup",
                        "start": 40,
                        "end": 51,
                    },
                ],
            },
        ]},
    )

    attribute: str = Field(examples=["rt.end_date"])
    severity: str | None = Field(default=None, examples=["high", "info"])
    rationale: str | None = None
    values: list[ConflictValue] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------

CITE_DESCRIPTION = "The cite token on the describe or fetch result this citation uses."
SUMMARY_DESCRIPTION = (
    "Two or three sentences of what that call shows: the finding, the date, and the "
    "measurement, so a reviewer can check the card without opening the file."
)


class ImagingCitation(BaseModel):
    """A DICOM describe or fetch: a preview slice, or series metadata.

    Describe what that slice or that metadata shows. An imaging citation has no
    agent, evidence, or conflicts. A finding from a note is its own note citation,
    with the token from that note's fetch.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [
            {
                "kind": "imaging",
                "cite": "c1",
                "summary": (
                    "Axial planning CT of the neck, slice 77 with the contours overlaid. "
                    "The GTVp outline sits at the glottic larynx."
                ),
            },
            {
                "kind": "imaging",
                "cite": "c2",
                "summary": (
                    "RTSTRUCT for that planning CT. "
                    "It names GTVp, Larynx, SpinalCord, and Esophagus."
                ),
                "fields": ["roi_names"],
            },
        ]},
    )

    kind: Literal["imaging"]
    cite: str = Field(description=CITE_DESCRIPTION, examples=["c1"])
    summary: str = Field(description=SUMMARY_DESCRIPTION)
    fields: list[str] | None = Field(
        default=None,
        description="Metadata keys that support the claim. Do not copy their values.",
        examples=[["roi_names"], ["SliceThickness", "PixelSpacing"]],
    )


class NoteCitation(BaseModel):
    """A clinical note read with describe or fetch.

    After fetch view=text, every claim from that note is one evidence item with its own
    quote from that text, and the same [cite:token] goes after each of those claims.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [
            {
                "kind": "note",
                "cite": "c3",
                "agent": "clinical_notes",
                "summary": (
                    "Radiation oncology completion note dated 13 February. "
                    "Treatment finished that day, 51 Gy in 20 fractions."
                ),
                "evidence": [
                    {
                        "n": 1,
                        "claim": "Treatment finished on February 13",
                        "quote": "Treatment completed February 13",
                    },
                    {
                        "n": 2,
                        "claim": "The dose was 51 Gy in 20 fractions",
                        "quote": "51 Gy in 20 fractions",
                    },
                ],
            },
        ]},
    )

    kind: Literal["note"]
    cite: str = Field(description=CITE_DESCRIPTION, examples=["c3"])
    summary: str = Field(description=SUMMARY_DESCRIPTION)
    evidence: list[Evidence] | None = Field(
        default=None,
        description="Required after fetch view=text: one item per claim taken from this note.",
    )
    conflicts: list[Conflict] | None = Field(
        default=None,
        description="Send when notes disagree about an attribute.",
    )
    agent: Literal["clinical_notes"] | None = None


class TableCitation(BaseModel):
    """A table read with describe or fetch."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [
            {
                "kind": "table",
                "cite": "c4",
                "summary": "Lab table. Hemoglobin was 13.1 and WBC 6.2 on the listed draw.",
                "fields": ["test", "value"],
            },
        ]},
    )

    kind: Literal["table"]
    cite: str = Field(description=CITE_DESCRIPTION, examples=["c4"])
    summary: str = Field(description=SUMMARY_DESCRIPTION)
    fields: list[str] | None = Field(
        default=None,
        description="Columns that support the claim.",
        examples=[["test", "value"]],
    )


class FileCitation(BaseModel):
    """A case file cited by path, only by an agent that did not call describe or fetch.

    web_path must be a file in the case resource list. The marker is [cite:] plus id.
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [
            {
                "kind": "file",
                "id": "1",
                "file": "2006-02-13-rt-completion.txt",
                "web_path": "/case/2006-02-13-rt-completion.txt",
                "summary": "Completion note. Treatment finished on 13 February.",
            },
        ]},
    )

    kind: Literal["file"]
    id: str = Field(examples=["1"])
    file: str = Field(examples=["2006-02-13-rt-completion.txt"])
    web_path: str = Field(examples=["/case/2006-02-13-rt-completion.txt"])
    summary: str = Field(description=SUMMARY_DESCRIPTION)
    agent: str | None = None
    evidence: list[Evidence] | None = None
    conflicts: list[Conflict] | None = None
    span_url: str | None = None


Citation = Annotated[
    ImagingCitation | NoteCitation | TableCitation | FileCitation,
    Field(discriminator="kind"),
]

# ---------------------------------------------------------------------------
# Whole answer
# ---------------------------------------------------------------------------


def _example(model: type[BaseModel], index: int = 0) -> dict:
    return model.model_config["json_schema_extra"]["examples"][index]


class CitedAnswer(BaseModel):
    """The whole reply after describe or fetch: one JSON object, nothing before or after it."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [
            {
                "response": (
                    "The planning CT shows the tumour at the glottic larynx [cite:c1]. "
                    "The structure set names it GTVp beside the larynx and spinal cord [cite:c2]. "
                    "Treatment finished on February 13 [cite:c3]. "
                    "The dose was 51 Gy in 20 fractions [cite:c3]."
                ),
                "citations": [
                    _example(ImagingCitation, 0),
                    _example(ImagingCitation, 1),
                    _example(NoteCitation),
                ],
            },
            {
                "response": "Treatment finished on 13 February [cite:1].",
                "citations": [_example(FileCitation)],
            },
        ]},
    )

    response: str = Field(
        description=(
            "The answer for the user. Put [cite:token] right after the words that call supports. "
            "Markers may not sit side by side, be grouped at the end, or be a sentence on their own."
        ),
    )
    citations: list[Citation] = Field(min_length=1)


EXAMPLE: dict = _example(CitedAnswer)

# ---------------------------------------------------------------------------
# What the agent is shown and sent
# ---------------------------------------------------------------------------


@cache
def prompt_schema() -> str:
    """The schema with descriptions and examples, for the system message."""
    return json.dumps(_clean(CitedAnswer.model_json_schema(), {"title"}))


@cache
def response_format() -> dict:
    """The strict structured-output request for an OpenAI-compatible endpoint."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cited_answer",
            "strict": True,
            "schema": strict_schema(CitedAnswer),
        },
    }


_NOT_STRICT = {
    "title",
    "examples",
    "default",
    "discriminator",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
}


def strict_schema(model: type[BaseModel]) -> dict:
    """The model's schema in the subset strict structured outputs accept.

    Every object lists all its properties as required and allows no others. Optional
    fields stay nullable. ``oneOf`` becomes ``anyOf``, ``const`` becomes a one-value
    ``enum``, and keywords strict mode rejects are dropped.
    """
    return _clean(model.model_json_schema(), _NOT_STRICT, strict=True)


def _clean(node: object, drop: set[str], strict: bool = False) -> object:
    if isinstance(node, list):
        return [_clean(item, drop, strict) for item in node]

    if not isinstance(node, dict):
        return node

    out: dict = {}

    for key, value in node.items():
        if key in drop:
            continue

        if key in ("properties", "$defs"):
            out[key] = {name: _clean(sub, drop, strict) for name, sub in value.items()}
        elif strict and key == "oneOf":
            out["anyOf"] = _clean(value, drop, strict)
        elif strict and key == "const":
            out["enum"] = [value]
        else:
            out[key] = _clean(value, drop, strict)

    if strict and out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])

    return out


# ---------------------------------------------------------------------------
# Checking one citation against its kind
# ---------------------------------------------------------------------------

_CITATION: TypeAdapter = TypeAdapter(Citation)
_KIND_BY_MODALITY = {"dicom": "imaging", "note": "note", "structured": "table"}
_SERVER_FILLED = ("id", "file", "web_path", "command", "dicom")
_NOTE_FIELDS = {"agent", "evidence", "conflicts"}


def kind_for(call: dict | None) -> str | None:
    """The citation kind a cite token's call requires, or None when the call is unknown."""
    if not isinstance(call, dict):
        return None

    if call.get("modality") == "dicom" or isinstance(call.get("dicom"), dict):
        return "imaging"

    return _KIND_BY_MODALITY.get(call.get("modality") or "")


def shape_problem(citation: dict, call: dict | None) -> str | None:
    """Why this citation does not fit the schema for its kind, or None.

    A citation without kind gets the kind of the call its token came from, or file
    when it has no token. Fields the server fills in on a cited call are ignored.
    """
    handle = citation.get("cite")
    marker = handle or citation.get("id")
    expected = kind_for(call) if handle else "file"
    given = citation.get("kind")

    if given is not None and expected is not None and given != expected:
        return (
            f"citation {marker} has kind {given!r}, but {handle or marker} "
            f"came from a call whose kind is {expected!r}"
        )

    kind = given or expected

    if kind is None:
        return None

    data = {
        key: value
        for key, value in citation.items()
        if not (handle and key in _SERVER_FILLED)
    }
    data["kind"] = kind

    try:
        _CITATION.validate_python(data)
    except ValidationError as exc:
        return f"citation {marker} is not a valid {kind} citation: {_brief(exc, kind, data)}"

    return None


def _brief(exc: ValidationError, kind: str, data: dict) -> str:
    parts = []

    for error in exc.errors():
        loc = [str(part) for part in error["loc"]]

        if loc and loc[0] == kind:
            loc = loc[1:]

        where = ".".join(loc) or "citation"

        if error["type"] == "extra_forbidden":
            parts.append(f"{where} is not allowed when kind is {kind!r}")
        else:
            parts.append(f"{where}: {error['msg']}")

    text = "; ".join(parts[:4])

    if kind == "imaging" and _NOTE_FIELDS & set(data):
        text += (
            ". An imaging citation describes the slice or metadata it fetched; "
            "cite a note with the token from that note's own fetch"
        )

    return text
