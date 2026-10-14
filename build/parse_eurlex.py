"""Parser for EUR-Lex / Publications Office XHTML (Official Journal acts such as the GDPR).

Chunk kinds:
  article     full article text (parent of its paragraphs)
  paragraph   numbered paragraph, including its lettered points (never split mid-list)
  definition  one defined term of the Art. 4 definitions list
  recital     one recital
Footnote markers are removed from the text and kept in `footnotes`.
"""
import re

import lxml.html

from common import norm, token_estimate

ART_ID = re.compile(r"^art_(\d+)$")
PARA_ID = re.compile(r"^(\d{3})\.(\d{3})$")
RCT_ID = re.compile(r"^rct_(\d+)$")
DEF_START = re.compile(r"^\((\d+)\)\s")


def load_tree(raw_text: str):
    t = re.sub(r"^<\?xml[^>]*\?>", "", raw_text)
    t = re.sub(r"<!DOCTYPE[^>]*>", "", t)
    return lxml.html.fromstring(t)


def collect_footnotes(root) -> dict:
    """Map note anchor id -> note text (marker stripped)."""
    notes = {}
    for p in root.xpath('//p[@class="oj-note"]'):
        a = p.find("a")
        if a is None or not a.get("id"):
            continue
        marker = a.text_content()
        text = norm(p.text_content())
        if text.startswith(marker):
            text = text[len(marker):].strip()
        notes[a.get("id")] = text
    return notes


class Extractor:
    def __init__(self, notes: dict):
        self.notes = notes
        self.found = []  # footnotes hit while extracting the current unit

    def inline(self, el) -> str:
        """Text of an element, dropping footnote reference anchors."""
        parts = [el.text or ""]
        for child in el:
            href = child.get("href") or ""
            if child.tag == "a" and href.startswith("#ntr"):
                self.found.append({"marker": norm(child.text_content()),
                                   "text": self.notes.get(href[1:], "")})
                parts[-1] = parts[-1].rstrip()  # no stray space where the marker was
            else:
                parts.append(self.inline(child))
            parts.append(child.tail or "")
        return "".join(parts)

    def lines(self, seq, depth=0):
        """Flatten a sequence of elements into (indent, text) lines."""
        out = []
        for ch in seq:
            if ch.tag == "p":
                s = norm(self.inline(ch))
                if s:
                    out.append((depth, s))
            elif ch.tag == "table":
                for tr in ch.xpath("./tbody/tr | ./thead/tr | ./tr"):
                    cells = [c for c in tr if c.tag == "td"]
                    if len(cells) == 2:
                        label = norm(self.inline(cells[0]))
                        sub = self.lines(list(cells[1]), depth + 1)
                        if sub:
                            out.append((depth, f"{label} {sub[0][1]}".strip()))
                            out.extend(sub[1:])
                        elif label:
                            out.append((depth, label))
                    else:
                        for c in cells:
                            out.extend(self.lines(list(c), depth))
            elif ch.tag == "div":
                out.extend(self.lines(list(ch), depth))
        return out

    @staticmethod
    def join(lines) -> str:
        return "\n".join("  " * d + s for d, s in lines)


def container_label(div):
    """(label, title) of a chapter or section div."""
    label = ""
    for p in div.iterchildren("p"):
        if (p.get("class") or "").startswith("oj-ti-section-1"):
            label = norm(p.text_content())
    title = ""
    for t in div.iterchildren("div"):
        if t.get("class") == "eli-title":
            title = norm(t.text_content())
    return label, title


def pretty_label(label: str) -> str:
    head, _, tail = label.partition(" ")
    return head.capitalize() + (" " + tail if tail else "")


def parse(raw_text: str, doc: dict, retrieved_at: str) -> list[dict]:
    root = load_tree(raw_text)
    ex = Extractor(collect_footnotes(root))
    doc_id = doc["doc_id"]
    short = doc.get("short_name", doc_id.upper())

    def mk(chunk_id, kind, ref, heading, text, hierarchy, parent, number, permalink):
        footnotes, ex.found = ex.found, []
        return {
            "chunk_id": chunk_id, "doc_id": doc_id, "kind": kind, "number": number,
            "hierarchy": hierarchy, "section_ref": ref, "heading": heading,
            "text": text, "parent_chunk_id": parent,
            "token_count": token_estimate(text), "footnotes": footnotes, "topics": [],
            "jurisdiction": doc["jurisdiction"], "doc_type": doc["doc_type"],
            "source_url": doc["source_url"], "retrieved_at": retrieved_at,
            "permalink": permalink,
        }

    chunks = []
    for art in root.xpath('//div[starts-with(@id,"art_")]'):
        m = ART_ID.match(art.get("id", ""))
        if not m:
            continue
        n = int(m.group(1))
        hier = []
        for anc in reversed(list(art.iterancestors("div"))):
            if (anc.get("id") or "").startswith("cpt_"):
                lab, tit = container_label(anc)
                hier.append(f"{pretty_label(lab)} - {tit}" if tit else pretty_label(lab))
        heading = ""
        body = []
        for c in art:
            if c.tag == "div" and c.get("class") == "eli-title":
                heading = norm(c.text_content())
            elif c.tag == "p" and c.get("class") == "oj-ti-art":
                continue
            else:
                body.append(c)
        art_hier = hier + [f"Article {n}"]
        art_id = f"{doc_id}:art:{n}"
        paras = [c for c in body if c.tag == "div" and PARA_ID.match(c.get("id", ""))]
        children, full = [], []

        if paras:
            for pdiv in paras:
                pn = int(PARA_ID.match(pdiv.get("id")).group(2))
                txt = ex.join(ex.lines(list(pdiv)))
                children.append(mk(f"{art_id}:{pn}", "paragraph", f"{short} Art. {n}({pn})",
                                   heading, txt, art_hier + [f"Paragraph {pn}"], art_id, pn,
                                   f"{doc_id}/art/{n}/#p{pn}"))
                full.append(txt)
        else:
            lines = ex.lines(body)
            starts = [i for i, (d, s) in enumerate(lines) if d == 0 and DEF_START.match(s)]
            if n == 4 and starts:
                full.append(ex.join(lines[:starts[0]]))
                bounds = starts + [len(lines)]
                for a, b in zip(bounds, bounds[1:]):
                    seg = lines[a:b]
                    dn = int(DEF_START.match(seg[0][1]).group(1))
                    txt = ex.join(seg)
                    tm = re.search(r"‘([^’]+)’", seg[0][1])
                    term = tm.group(1) if tm else ""
                    c = mk(f"{art_id}:{dn}", "definition", f"{short} Art. {n}({dn})",
                           f"Definition: {term}" if term else heading, txt,
                           art_hier + [f"Definition ({dn})"], art_id, dn,
                           f"{doc_id}/art/{n}/#p{dn}")
                    c["defined_term"] = term
                    children.append(c)
                    full.append(txt)
            else:
                txt = ex.join(lines)
                children.append(mk(f"{art_id}:1", "paragraph", f"{short} Art. {n}", heading,
                                   txt, art_hier, art_id, 1, f"{doc_id}/art/{n}/"))
                children[-1]["unnumbered"] = True
                full.append(txt)

        a = mk(art_id, "article", f"{short} Art. {n}", heading, "\n".join(full),
               art_hier, None, n, f"{doc_id}/art/{n}/")
        a["footnotes"] = [f for c in children for f in c["footnotes"]]
        a["child_chunk_ids"] = [c["chunk_id"] for c in children]
        chunks.append(a)
        chunks.extend(children)

    for rd in root.xpath('//div[starts-with(@id,"rct_")]'):
        m = RCT_ID.match(rd.get("id", ""))
        if not m:
            continue
        n = int(m.group(1))
        txt = ex.join(ex.lines(list(rd)))
        txt = re.sub(r"^\(%d\)\s*" % n, "", txt)  # the number is the label, not text
        chunks.append(mk(f"{doc_id}:rct:{n}", "recital", f"{short} Recital {n}", "", txt,
                         ["Recitals", f"Recital {n}"], None, n, f"{doc_id}/rct/{n}/"))
    return chunks
