"""Shared paths and helpers for the ingestion pipeline."""
import hashlib
import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "data" / "reports"


def load_sources() -> dict:
    docs = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["documents"]
    return {d["doc_id"]: d for d in docs}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(s: str) -> str:
    """Collapse all whitespace (including non-breaking spaces) to single spaces."""
    return re.sub(r"\s+", " ", s).strip()


def write_json(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def token_estimate(text: str) -> int:
    """Rough token count (words * 1.3); good enough for size ceilings."""
    return round(len(text.split()) * 1.3)
