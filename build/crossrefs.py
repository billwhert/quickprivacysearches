"""Extract explicit "Article N(M)" references from chunk text (first-pass, reviewable)."""
import re

ART_REF = re.compile(
    r"\bArticles?\s+(?P<first>\d+)(?:\((?P<para>\d+)\))?"
    r"(?P<rest>(?:\s*(?:,|and|or|to)\s*\d+(?:\(\d+\))?)*)"
)
REST_ITEM = re.compile(r"(,|and|or|to)\s*(\d+)(?:\((\d+)\))?")
EXTERNAL = re.compile(r"^[^.;]{0,80}?\bof\s+(?:Council\s+)?(?:Directive|Regulation|Decision|Treaty|Convention|Framework)\b"
                      r"(?!\s+\(EU\)\s+2016/679)", re.I)
TREATY = re.compile(r"^\s*(?:TFEU|TEU)(?![A-Za-z])")


def extract(chunks: list[dict]) -> list[dict]:
    ids = {c["chunk_id"] for c in chunks}
    refs = []
    for c in chunks:
        if c["kind"] == "article":
            continue
        text = c["text"]
        doc = c["doc_id"]
        for m in ART_REF.finditer(text):
            tail = text[m.end():m.end() + 100]
            external = bool(TREATY.match(tail) or EXTERNAL.match(tail)) and not tail.lstrip().startswith("of this Regulation")
            targets = [(int(m["first"]), m["para"])]
            prev = int(m["first"])
            for op, num, para in REST_ITEM.findall(m["rest"] or ""):
                num = int(num)
                if op == "to" and num > prev:
                    targets.extend((k, None) for k in range(prev + 1, num))
                targets.append((num, para or None))
                prev = num
            for art, para in targets:
                tid = f"{doc}:art:{art}"
                if para and f"{tid}:{para}" in ids:
                    tid = f"{tid}:{para}"
                refs.append({
                    "from_chunk_id": c["chunk_id"],
                    "raw": m.group(0).strip(),
                    "to_chunk_id": tid if tid in ids and not external else None,
                    "external": external,
                })
    return refs
