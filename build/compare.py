"""Comparison sets: the same question answered by several laws, side by side (compare/*.yaml).

Sets are written by hand, not generated. Exact text is pulled from the stored provisions.
"""
import yaml

from common import ROOT

COMPARE_DIR = ROOT / "compare"


def load_sets() -> list[dict]:
    sets = []
    for p in sorted(COMPARE_DIR.glob("*.yaml")):
        s = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        s["_path"] = p
        sets.append(s)
    return sets


def validate(sets: list[dict], by_id: dict, loaded_docs: set) -> list[str]:
    errs, ids = [], set()
    for s in sets:
        name = s.get("id", s["_path"].name)
        for field in ("id", "title", "question", "columns"):
            if not s.get(field):
                errs.append(f"{name}: missing '{field}'")
        if s.get("id") in ids:
            errs.append(f"{name}: duplicate comparison id")
        ids.add(s.get("id"))
        cols = s.get("columns") or []
        if len(cols) < 2:
            errs.append(f"{name}: a comparison needs at least two columns")
        seen_docs = set()
        for i, col in enumerate(cols, 1):
            if col.get("doc") not in loaded_docs:
                errs.append(f"{name}: column {i} uses '{col.get('doc')}', which is not a loaded document")
            if col.get("doc") in seen_docs:
                errs.append(f"{name}: document '{col.get('doc')}' appears in two columns")
            seen_docs.add(col.get("doc"))
            if not col.get("heading") or not col.get("chunk_ids"):
                errs.append(f"{name}: column {i} needs a heading and chunk_ids")
            for cid in col.get("chunk_ids") or []:
                if cid not in by_id:
                    errs.append(f"{name}: cites '{cid}', which is not in the loaded text")
                elif by_id[cid]["doc_id"] not in (col.get("docs") or [col.get("doc")]):
                    errs.append(f"{name}: '{cid}' is not part of this column's document(s) "
                                f"{col.get('docs') or [col.get('doc')]}")
    return errs
