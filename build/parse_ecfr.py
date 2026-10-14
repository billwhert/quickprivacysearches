"""Parser for eCFR renderer HTML (US federal regulations, e.g. 45 CFR Parts 160 and 164).

The eCFR gives every paragraph an id built from its citation, e.g. `p-164.502(b)(1)` or, in
definitions, `p-164.501(Marketing)(1)`. We use those ids for the hierarchy instead of guessing.

Units: section (parent), top-level paragraph (a), (b)... (searchable; split into its children
only when longer than the ceiling), and one definition per defined term in definitions sections.
"""
import json
import pathlib
import re
import urllib.parse

import lxml.html

from common import norm, token_estimate

CEILING_TOKENS = 1500
GROUP_RE = re.compile(r"\(([^()]*)\)")


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


class Node:
    def __init__(self, path, term="", heading=""):
        self.path, self.term, self.heading = tuple(path), term, heading
        self.lines: list[str] = []
        self.children: list["Node"] = []

    def render(self, indent=0) -> str:
        out = ["  " * indent + l for l in self.lines]
        for c in self.children:
            out.append(c.render(indent + 1))
        return "\n".join(x for x in out if x.strip())

    def own_text(self) -> str:
        return " ".join(self.lines).strip()

    def labels(self) -> list[str]:
        """Label path used in chunk ids and anchors (definitions use a slug of the term)."""
        if self.term and len(self.path) >= 1:
            return [slug(self.term)] + list(self.path[1:])
        return list(self.path)


def parse_section(div):
    """Return (title_line, top-level nodes, history/note lines, lead-in lines) for a section div.

    Nesting follows eCFR's own indent levels (indent-1, indent-2, ...). Labels come from the
    paragraph ids, but a paragraph's parent is whatever sits one level above it in the text, which
    is robust to the occasional wrong id in the source (e.g. a "Business associate" item that
    carries the id of the preceding definition).
    """
    h4 = div.find("h4")
    title_line = norm(h4.text_content()) if h4 is not None else ""
    top: list[Node] = []
    stack: list[tuple[int, Node]] = []
    notes, lead = [], []
    last = None
    for p in div.iter("p"):
        cls = (p.get("class") or "").split()
        text = norm(p.text_content())
        if not text:
            continue
        if "citation" in cls:
            notes.append(text)
            continue
        # the canonical id ("p-164.502(b)(1)") sits on the paragraph or on the div that wraps it
        ref, el = "", p
        while el is not None and el is not div:
            if (el.get("id") or "").startswith("p-"):
                ref = urllib.parse.unquote(el.get("id")[2:])
                break
            el = el.getparent()
        groups = GROUP_RE.findall(ref)
        indent = next((int(c.split("-")[1]) for c in cls if re.fullmatch(r"indent-\d+", c)), 0)
        if not groups or not indent:
            if last is not None:       # undesignated paragraph continuing the previous provision
                last.lines.append(text)
            else:
                lead.append(text)
            continue
        em = p.find("em")
        is_def = em is not None and "paragraph-hierarchy" in (em.get("class") or "")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        path = (parent.path if parent else ()) + (groups[-1],)
        ph = p.xpath('.//em[contains(@class,"paragraph-heading")]')
        node = Node(path, norm(em.text_content()).strip(" :,;.") if is_def else "",
                    norm(ph[0].text_content()) if ph else "")
        node.lines.append(text)
        if parent is not None:
            parent.children.append(node)
        else:
            top.append(node)
        stack.append((indent, node))
        last = node
    return title_line, top, notes, lead


def parse(files: dict, doc: dict, retrieved_at: str, raw_root: pathlib.Path):
    """files: {part: {"html": rel path, "structure": rel path}}. Returns (chunks, expected_sections)."""
    doc_id, short = doc["doc_id"], doc["short_name"]
    chunks: list[dict] = []
    expected: list[str] = []

    def mk(cid, kind, ref, heading, text, hier, parent, number, permalink, source_url, **extra):
        c = {"chunk_id": cid, "doc_id": doc_id, "kind": kind, "number": number, "hierarchy": hier,
             "section_ref": ref, "heading": heading, "text": text, "parent_chunk_id": parent,
             "token_count": token_estimate(text), "footnotes": [], "topics": [],
             "jurisdiction": doc["jurisdiction"], "doc_type": doc["doc_type"],
             "source_url": source_url, "retrieved_at": retrieved_at, "permalink": permalink}
        c.update(extra)
        return c

    for part in sorted(files, key=int):
        struct = json.loads((raw_root / files[part]["structure"]).read_text(encoding="utf-8"))

        def collect(n):
            if n.get("type") == "section" and not n.get("reserved"):
                expected.append(n["identifier"])
            elif n.get("type") == "appendix" and not n.get("reserved"):
                expected.append(slug(n["identifier"]))
            for ch in n.get("children", []):
                collect(ch)
        collect(struct)

        root = lxml.html.fromstring((raw_root / files[part]["html"]).read_text(encoding="utf-8"))
        h1 = root.find(".//h1")
        ptitle = norm(h1.text_content()) if h1 is not None else ""
        part_label = f"Part {part}"
        if "—" in ptitle:
            small = {"and", "of", "the", "for", "to", "in", "a", "an", "or"}
            words = ptitle.split("—", 1)[1].strip().lower().split()
            part_label += " - " + " ".join(w if (i and w in small) else w.capitalize()
                                           for i, w in enumerate(words))

        for sub in root.xpath('.//div[contains(@class,"subpart")]'):
            h2 = sub.find("h2")
            sub_title = norm(h2.text_content()).replace("—", " - ") if h2 is not None else ""
            for div in sub.xpath('./div[contains(@class,"section") or contains(@class,"appendix")]'):
                sid = div.get("id")
                is_app = "appendix" in (div.get("class") or "")
                title_line, nodes, notes, lead = parse_section(div)
                if is_app:
                    num = slug(sid)
                    head_parts = title_line.split("—", 1)
                    sec_ref = f"{short} {head_parts[0].strip()}"
                    heading = head_parts[1].strip() if len(head_parts) > 1 else title_line
                    permalink = f"{doc_id}/sec/{num}/"
                    src = f"https://www.ecfr.gov/current/title-45/part-{part}"
                    rows = []                     # the appendix is a table: one line per row
                    for tr in div.iter("tr"):
                        cells = [norm(c.text_content()) for c in tr if c.tag in ("td", "th")]
                        if any(cells):
                            rows.append(" | ".join(cells))
                    table = Node(())
                    table.lines = rows
                    nodes, lead = [table], []
                    hier = [part_label, sub_title, sec_ref.removeprefix(short + " ")]
                else:
                    num = sid
                    m = re.match(r"^§\s*" + re.escape(sid) + r"\s*(.*)$", title_line)
                    heading = (m.group(1) if m else title_line).strip().rstrip(".")
                    sec_ref = f"{short} § {sid}"
                    permalink = f"{doc_id}/sec/{sid}/"
                    src = f"https://www.ecfr.gov/current/title-45/section-{sid}"
                    hier = [part_label, sub_title, f"Section {sid}"]
                sec_id = f"{doc_id}:sec:{num}"
                children: list[dict] = []

                def emit(node, lead_in=""):
                    labels = node.labels()
                    key = ".".join(labels)
                    cid = f"{sec_id}:{key}" if key else f"{sec_id}:0"
                    is_def = bool(node.term) and len(node.path) == 1
                    ref = sec_ref + "".join(f"({g})" for g in node.path)
                    frag = f"p{key}" if key else ""
                    extra = {}
                    if is_def:
                        extra["defined_term"] = node.term
                    if lead_in:
                        extra["lead_in"] = lead_in
                    if node.heading:
                        extra["subheading"] = node.heading
                    path_h = ([f"Definition: {node.term}"] + [f"({g})" for g in node.path[1:]]) if node.term \
                        else [f"({g})" for g in node.path]
                    children.append(mk(
                        cid, "definition" if is_def else "paragraph", ref,
                        f"Definition: {node.term}" if is_def else heading, node.render(),
                        hier + path_h, sec_id, key or "0",
                        permalink + (f"#{frag}" if frag else ""), src, **extra))

                def walk(node, lead_in=""):
                    if token_estimate(node.render()) > CEILING_TOKENS and node.children:
                        own = node.own_text()
                        carried = (lead_in + " " + own).strip() if lead_in else own
                        for ch in node.children:
                            walk(ch, carried)
                    else:
                        emit(node, lead_in)

                if lead:
                    ln = Node(())
                    ln.lines = lead
                    emit(ln)
                for node in nodes:
                    walk(node)
                if not children:
                    continue
                parent = mk(sec_id, "section", sec_ref, heading, "\n".join(c["text"] for c in children),
                            hier, None, num, permalink, src,
                            child_chunk_ids=[c["chunk_id"] for c in children])
                if notes:
                    parent["note"] = " ".join(notes)
                chunks.append(parent)
                chunks.extend(children)
    return chunks, expected
