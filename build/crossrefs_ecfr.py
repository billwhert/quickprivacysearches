"""Cross-references inside 45 CFR Parts 160/164: "164.502(b)", "§ 164.514(b)(2)(i)", "§§ 164.506 and 164.508"."""
import re

REF = re.compile(r"(?<![\d.])(?P<num>16[04]\.\d{3})(?P<subs>(?:\([A-Za-z0-9]{1,4}\))*)(?!\d)")
SUB = re.compile(r"\(([A-Za-z0-9]{1,4})\)")


def extract(chunks: list[dict], all_ids: set, own_doc: str) -> list[dict]:
    refs = []
    for c in chunks:
        if c["kind"] == "section":
            continue
        seen = set()
        for m in REF.finditer(c["text"]):
            num = m.group("num")
            sec = f"{own_doc}:sec:{num}"
            labels = SUB.findall(m.group("subs") or "")
            tid = sec
            for n in range(len(labels), 0, -1):    # deepest chunk that exists
                cand = f"{sec}:{'.'.join(labels[:n])}"
                if cand in all_ids:
                    tid = cand
                    break
            raw = m.group(0)
            if (tid, raw) in seen:
                continue
            seen.add((tid, raw))
            refs.append({"from_chunk_id": c["chunk_id"], "raw": raw,
                         "to_chunk_id": tid if sec in all_ids else None,
                         "external": False, "own_space": True})
    return refs
