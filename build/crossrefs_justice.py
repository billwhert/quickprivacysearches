"""Cross-references inside a Justice Laws Act: "subsection 7(3)", "paragraph 7(3)(d.1)", "clause 4.3 of Schedule 1"."""
import re

SEC = re.compile(r"\b(?:subsections?|sections?|paragraphs?)\s+(?P<num>\d+(?:\.\d+)?)(?P<subs>(?:\([A-Za-z0-9.]+\))*)")
CLAUSE = re.compile(r"\bclauses?\s+(?P<cl>4\.\d+(?:\.\d+)*)")
SUB = re.compile(r"\(([A-Za-z0-9.]+)\)")
# "section 7 of the Criminal Code" points at another Act; "of this Act" does not
OTHER_ACT = re.compile(
    r"^\s*(?:(?:and|or|to)\s+\d+(?:\.\d+)?(?:\([A-Za-z0-9.]+\))*\s*,?\s*)*"
    r"(?:of|under)\s+(?:the\s+(?!Act\b)[A-Z]|that\s+Act)")


def extract(chunks: list[dict], all_ids: set, own_doc: str) -> list[dict]:
    refs = []
    for c in chunks:
        if c["kind"] == "section":
            continue
        text = c["text"]
        seen = set()
        for m in SEC.finditer(text):
            external = bool(OTHER_ACT.match(text[m.end():m.end() + 60]))
            num = m.group("num")
            sec = f"{own_doc}:sec:{num}"
            labels = SUB.findall(m.group("subs") or "")
            tid = sec
            for n in range(len(labels), 0, -1):
                cand = f"{sec}:{'.'.join(labels[:n])}"
                if cand in all_ids:
                    tid = cand
                    break
            key = (tid, m.group(0))
            if key in seen:
                continue
            seen.add(key)
            refs.append({"from_chunk_id": c["chunk_id"], "raw": m.group(0).strip(),
                         "to_chunk_id": tid if sec in all_ids and not external else None,
                         "external": external, "own_space": not external})
        for m in CLAUSE.finditer(text):
            cl = m.group("cl")
            parts = cl.split(".")
            sec = f"{own_doc}:sec:sched1-{parts[0]}.{parts[1]}"
            tid = f"{sec}:{cl}" if f"{sec}:{cl}" in all_ids else sec
            key = (tid, m.group(0))
            if key in seen:
                continue
            seen.add(key)
            refs.append({"from_chunk_id": c["chunk_id"], "raw": m.group(0).strip(),
                         "to_chunk_id": tid if sec in all_ids else None, "external": False, "own_space": True})
    return refs
