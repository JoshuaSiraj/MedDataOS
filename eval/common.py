"""Shared eval helpers: env loading, paths, patient_info (with modality stripping)."""
import json
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data"
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)
PINFO = ROOT / "multimodal-data" / "patient-info"


def run_dir(tag):
    """Per-run results folder (eval/results/<tag>/), created on demand.
    Each run stores its raw stage outputs + manifest + REPORT here so it is
    self-contained and browsable by others."""
    d = RESULTS / tag
    d.mkdir(parents=True, exist_ok=True)
    return d

MODALITIES = ["clinical_notes", "chest_xray", "ecg", "echo", "heart_sounds", "lab_results", "medication"]

# map agent modality key -> data_dates key used in patient-info json
AGENT_TO_DATADATE = {
    "clinical_notes": "clinical-notes", "chest_xray": "chest-xray", "ecg": "ecg",
    "echo": "echo", "heart_sounds": "heart-sounds", "lab_results": "lab-results",
    "medication": "medications",
}


def load_patient_info(pid, strip_modalities=None):
    """Load patient-info json. strip_modalities: list of agent keys to remove from
    data_dates so the system treats them as unavailable (for unavailable-modality probes)."""
    info = json.loads((PINFO / f"{pid}.json").read_text())
    if strip_modalities:
        dd = dict(info.get("data_dates", {}))
        for m in strip_modalities:
            dd.pop(AGENT_TO_DATADATE.get(m, m), None)
        info["data_dates"] = dd
    return info


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
