"""Cross-references in statute/regulation text: "Section 1798.105", "section 7011, subsection (a)"."""
import re

CIV = re.compile(r"\b(?:Civil Code,?\s+)?[Ss]ections?\s+(?P<num>1798\.\d+(?:\.\d+)?)"
                 r"(?:,?\s*(?:subdivision|subd\.)\s*\((?P<sub>[a-z]{1,2})\))?")
CIV_BARE = re.compile(r"(?<![\d.])(?P<num>1798\.\d+(?:\.\d+)?)(?!\d)(?:\s*\((?P<sub>[a-z]{1,2})\))?")
REG = re.compile(r"\b[Ss]ections?\s+(?P<num>7\d{3})(?!\d)"
                 r"(?:,?\s*(?:subsection|subdivision)\s*\((?P<sub>[a-z]{1,2})\))?")


def _in_own_space(doc: str, num: str) -> bool:
    """CCPA proper is 1798.100 onward; 1798.80-1798.99 are other parts of the Civil Code."""
    if doc != "ccpa":
        return True
    parts = [int(x) for x in num.split(".")]
    return parts[0] == 1798 and parts[1] >= 100


def extract(chunks: list[dict], all_ids: set, own_doc: str) -> list[dict]:
    """own_doc is the doc_id being ingested; refs into its own number space must resolve."""
    refs = []
    for c in chunks:
        if c["kind"] == "section":
            continue
        text = c["text"]
        found, spans = [], []
        for m in CIV.finditer(text):
            found.append(("ccpa", m.group("num"), m.group("sub"), m.group(0)))
            spans.append(m.span())
        for m in CIV_BARE.finditer(text):
            if any(a <= m.start() < b for a, b in spans):
                continue
            found.append(("ccpa", m.group("num"), m.group("sub"), m.group(0)))
        for m in REG.finditer(text):
            found.append(("ccpa_regs", m.group("num"), m.group("sub"), m.group(0)))
        seen = set()
        for doc, num, sub, raw in found:
            sec = f"{doc}:sec:{num}"
            tid = f"{sec}:{sub}" if sub and f"{sec}:{sub}" in all_ids else sec
            if (tid, raw) in seen:
                continue
            seen.add((tid, raw))
            refs.append({"from_chunk_id": c["chunk_id"], "raw": raw.strip(),
                         "to_chunk_id": tid if sec in all_ids else None,
                         "external": doc != own_doc and sec not in all_ids,
                         "own_space": doc == own_doc and _in_own_space(doc, num)})
    return refs
