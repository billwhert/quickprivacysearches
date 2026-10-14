"""Parser for Justice Laws (Canada) consolidated Act XML (the "LIMS" schema), e.g. PIPEDA.

Units
  section     parent: a numbered section of the Act, or one principle of Schedule 1, or a table schedule
  paragraph   a subsection (or the whole section when it has none); split into its paragraphs if too long
  definition  one defined term (section 2(1) and similar)
Schedule 1 principles (the CSA Model Code) become sections `sched1-4.1` ... `sched1-4.10`; each numbered
clause (4.1.1, 4.1.2 ...) is one provision.
"""
import pathlib
import re

from lxml import etree

from common import norm, token_estimate

CEILING_TOKENS = 1500
LIST_TAGS = {"Subsection", "Paragraph", "Subparagraph", "Clause", "Subclause", "Subsubclause", "Definition"}
BASE = "https://laws-lois.justice.gc.ca/eng/acts/P-8.6/FullText.html"


def ln(el) -> str:
    return etree.QName(el).localname


def inline(el) -> str:
    """All text of an inline element (Text), without footnote reference markers."""
    parts = [el.text or ""]
    for ch in el:
        if ln(ch) != "FootnoteRef":
            parts.append(inline(ch))
        parts.append(ch.tail or "")
    return "".join(parts)


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


class N:
    """A block of the Act: label, ordered items (own text lines and child blocks)."""

    def __init__(self, label=""):
        self.label = label
        self.items: list = []        # ("t", str) | ("n", N)
        self.note = ""               # marginal note, when present

    def kids(self):
        return [x for k, x in self.items if k == "n"]

    def own_text(self) -> str:
        return " ".join(x for k, x in self.items if k == "t").strip()

    def render(self, indent=0) -> str:
        out, first = [], True
        has_head = bool(self.label) or any(k == "t" for k, _ in self.items)
        child_indent = indent + 1 if has_head else indent
        for kind, x in self.items:
            if kind == "t":
                line = (f"{self.label} " if first and self.label else "") + x
                out.append("  " * indent + line.strip())
                first = False
            else:
                if first and self.label:           # a label with no text of its own
                    out.append("  " * indent + self.label)
                    first = False
                out.append(x.render(child_indent))
        if first and self.label:
            out.append("  " * indent + self.label)
        return chr(10).join(l for l in out if l.strip())


def build(el) -> N:
    lbl = el.find("Label")
    n = N(norm(inline(lbl)) if lbl is not None else "")
    mn = el.find("MarginalNote")
    if mn is not None:
        n.note = norm(inline(mn))
    for ch in el:
        t = ln(ch)
        if t == "Text":
            s = norm(inline(ch))
            if s:
                n.items.append(("t", s))
        elif t in LIST_TAGS:
            n.items.append(("n", build(ch)))
        elif t.startswith("Continued"):
            for tx in ch.findall("Text"):
                s = norm(inline(tx))
                if s:
                    n.items.append(("t", s))
    return n


def heading_text(h) -> str:
    bits = [norm(inline(x)) for x in h if ln(x) in ("Label", "TitleText")]
    return " - ".join(b for b in bits if b)


def parse(path: pathlib.Path, doc: dict, retrieved_at: str):
    root = etree.fromstring(path.read_bytes())
    doc_id, short = doc["doc_id"], doc["short_name"]
    chunks: list[dict] = []
    expected: list[str] = []

    def mk(cid, kind, ref, heading, text, hier, parent, number, permalink, src, **extra):
        c = {"chunk_id": cid, "doc_id": doc_id, "kind": kind, "number": number, "hierarchy": hier,
             "section_ref": ref, "heading": heading, "text": text, "parent_chunk_id": parent,
             "token_count": token_estimate(text), "footnotes": [], "topics": [],
             "jurisdiction": doc["jurisdiction"], "doc_type": doc["doc_type"],
             "source_url": src, "retrieved_at": retrieved_at, "permalink": permalink}
        c.update(extra)
        return c

    def add_section(num, ref, heading, hier, lims_id, pieces, note=""):
        """pieces: list of dicts {key, label, text, kind, term, lead, sub}. Emits parent + children."""
        sec_id = f"{doc_id}:sec:{num}"
        permalink = f"{doc_id}/sec/{num}/"
        src = f"{BASE}#{lims_id}" if lims_id else BASE
        kids = []
        for p in pieces:
            key = p["key"]
            frag = f"p{key}" if key not in ("", "0") else ""
            extra = {}
            if p.get("term"):
                extra["defined_term"] = p["term"]
            if p.get("lead"):
                extra["lead_in"] = p["lead"]
            if p.get("sub"):
                extra["subheading"] = p["sub"]
            if p.get("label"):
                extra["label"] = p["label"]
            kids.append(mk(f"{sec_id}:{key or '0'}", p.get("kind", "paragraph"), p["ref"],
                           f"Definition: {p['term']}" if p.get("term") else heading, p["text"],
                           hier + p.get("hier", []), sec_id, key or "0",
                           permalink + (f"#{frag}" if frag else ""), src, **extra))
        if not kids:
            return
        parent = mk(sec_id, "section", ref, heading, chr(10).join(k["text"] for k in kids), hier, None, num,
                    permalink, src, child_chunk_ids=[k["chunk_id"] for k in kids])
        if note:
            parent["note"] = note
        chunks.append(parent)
        chunks.extend(kids)
        expected.append(num)

    def split(node: N, key: str, ref: str, lead="", extra_hier=None, sub=""):
        """Yield pieces for a block; split into child blocks when it exceeds the size ceiling."""
        text = node.render()
        kids = node.kids()
        label = key.split(".")[-1]
        if token_estimate(text) > CEILING_TOKENS and kids:
            own = node.own_text()
            carried = (lead + " " + (node.label + " " if node.label else "") + own).strip()
            out = []
            for k in kids:
                kl = re.sub(r"[()\s]", "", k.label) or slug(k.own_text()[:20])
                out += split(k, f"{key}.{kl}", f"{ref}({kl})", carried, extra_hier, "")
            return out
        return [{"key": key, "ref": ref, "text": text, "lead": lead, "sub": sub or node.note,
                 "hier": extra_hier or []}]

    # ---------------- body: sections ----------------
    footnotes = {f.get("id"): norm(inline(f)) for f in root.iter("Footnote") if f.get("id")}
    body = root.find("Body")
    stack = ["", "", ""]
    for el in body:
        t = ln(el)
        if t == "Heading":
            lvl = max(1, min(3, int(el.get("level") or 1)))
            stack[lvl - 1] = heading_text(el)
            for i in range(lvl, 3):
                stack[i] = ""
            continue
        if t != "Section":
            continue
        lbl = el.find("Label")
        num = norm(inline(lbl)) if lbl is not None else ""
        if not num:
            continue
        note = " ".join(dict.fromkeys(footnotes[r.get("idref")] for r in el.iter("FootnoteRef")
                                      if r.get("idref") in footnotes))
        heading = norm(inline(el.find("MarginalNote"))) if el.find("MarginalNote") is not None else ""
        hier = [x for x in stack if x] + [f"Section {num}"]
        ref = f"{short} s. {num}"
        pieces = []
        subs = [c for c in el if ln(c) == "Subsection"]
        if subs:
            lead_texts = [norm(inline(c)) for c in el if ln(c) == "Text"]
            if any(lead_texts):
                pieces.append({"key": "0", "ref": ref, "text": " ".join(x for x in lead_texts if x),
                               "hier": []})
            for sub in subs:
                node = build(sub)
                lab = re.sub(r"[()\s]", "", node.label) or "0"
                dnodes = [c for c in sub if ln(c) == "Definition"]
                if dnodes:
                    lead = N(node.label)
                    lead.items = [("t", node.own_text())] if node.own_text() else []
                    pieces.append({"key": lab, "ref": f"{ref}({lab})", "text": lead.render(),
                                   "hier": [f"Subsection ({lab})"]})
                    for dn in dnodes:
                        term_el = dn.find(".//DefinedTermEn")
                        term = norm(inline(term_el)) if term_el is not None else ""
                        dn_node = build(dn)
                        pieces.append({"key": slug(term) or f"d{len(pieces)}", "ref": f"{ref}({lab}) \"{term}\"",
                                       "text": dn_node.render(), "kind": "definition", "term": term,
                                       "hier": [f"Subsection ({lab})", f"Definition: {term}"]})
                else:
                    pieces += split(node, lab, f"{ref}({lab})", extra_hier=[f"Subsection ({lab})"])
        else:
            node = build(el)
            node.label = ""
            pieces += split(node, "0", ref)
        add_section(num, ref, heading, hier, el.get("{http://justice.gc.ca/lims}id"), pieces, note=note)

    # ---------------- Schedule 1: the ten principles ----------------
    sched = root.findall("Schedule")
    s1 = sched[0]
    s1_head = norm(" ".join(inline(x) for x in s1.find("ScheduleFormHeading") if ln(x) == "TitleText"))
    s1_hier = [f"Schedule 1 - {s1_head}"]
    di = s1.find("DocumentInternal")
    groups: list[tuple[str, list]] = []
    for el in di:
        if ln(el) == "GroupHeading":
            groups.append((norm(inline(el.find("TitleText"))), []))
        elif groups:
            groups[-1][1].append(el)

    def prov_lines(p, depth=0) -> list[tuple[int, str]]:
        out = []
        lab = p.find("Label")
        prefix = norm(inline(lab)) + " " if lab is not None else ""      # list items carry "(a)" in a Label
        for ch in p:
            t = ln(ch)
            if t == "Text":
                s = norm(inline(ch))
                if s:
                    out.append((depth, prefix + s))
                    prefix = ""
            elif t == "Provision":
                out.extend(prov_lines(ch, depth + 1))
        return out

    for title, provs in groups:
        m = re.match(r"^(4\.\d+)\s+(.*)$", title)
        if not m:
            continue
        clause, name = m.group(1), m.group(2).strip()
        sec_num = f"sched1-{clause}"
        pieces, cur = [], None
        for p in provs:
            lines = prov_lines(p)
            if not lines:
                continue
            first = lines[0][1]
            if re.fullmatch(r"\d+\.\d+(?:\.\d+)*", first):        # a numbered clause: "4.1.1"
                rest = lines[1:]
                body_lines = [(max(0, d - 1), s) for d, s in rest] or [(0, "")]
                body_lines[0] = (body_lines[0][0], f"{first} {body_lines[0][1]}".strip())
                cur = {"key": first, "ref": f"{short} Sched. 1, cl. {first}", "label": first,
                       "lines": body_lines, "hier": [f"Clause {first}"]}
                pieces.append(cur)
            elif cur is None and not pieces:                       # the principle's statement
                cur = {"key": "0", "ref": f"{short} Sched. 1, cl. {clause}", "label": clause,
                       "lines": [(d, s) for d, s in lines], "hier": [name]}
                pieces.append(cur)
            else:                                                  # trailing or note text continues the last clause
                cur["lines"].extend((d + 1, s) for d, s in lines)
        for pc in pieces:
            pc["text"] = "\n".join("  " * d + s for d, s in pc.pop("lines"))
        add_section(sec_num, f"{short} Sched. 1, cl. {clause}", name.replace("—", "-").replace("�", "-"),
                    s1_hier + [title.replace("—", "-").replace("�", "-")],
                    s1.get("{http://justice.gc.ca/lims}id"), pieces)

    # ---------------- Schedules 2 to 4: tables ----------------
    for idx, sc in enumerate(sched[1:], 2):
        if sc.get("id") == "NifProvs":
            continue
        fh = sc.find("ScheduleFormHeading")
        label = norm(fh.findtext("Label") or f"SCHEDULE {idx}") if fh is not None else f"SCHEDULE {idx}"
        sub = norm(inline(fh.find("OriginatingRef"))) if fh is not None and fh.find("OriginatingRef") is not None else ""
        lines = []
        for table in sc.iter("table"):
            ttl = table.find("title")
            if ttl is not None:
                lines.append(norm(inline(ttl)))
            for row in table.iter("row"):
                cells = [norm(inline(e)) for e in row.findall("entry")]
                cells = [c for c in cells if c]
                if cells:
                    lines.append(" | ".join(cells))
        groups_, cur_ = [], []
        for line in lines:
            if cur_ and token_estimate("\n".join(cur_ + [line])) > 1100:
                groups_.append(cur_)
                cur_ = []
            cur_.append(line)
        if cur_:
            groups_.append(cur_)
        n = len(groups_)
        pieces = [{"key": str(i) if n > 1 else "0", "ref": f"{short} {label.title()}" + (f" (part {i} of {n})" if n > 1 else ""),
                   "text": "\n".join(g), "hier": []} for i, g in enumerate(groups_, 1)]
        add_section(f"sched{idx}", f"{short} {label.title()}", sub or label.title(), [label.title()],
                    sc.get("{http://justice.gc.ca/lims}id"), pieces)
    return chunks, expected
