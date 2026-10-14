"""Parser for US legal-code documents delivered as PDF or plain text (CCPA statute, CPPA regulations,
CalOPPA). One section = one parent chunk; each top-level subdivision = one searchable chunk
(split further only when it is too long); definitions sections are chunked per defined term.

Structure inside a section follows California drafting convention:
    (a) -> (1) -> (A) -> (i) -> (I)
The parser accepts a label only when it is the expected next sibling or the first child of the
open node, so citations that happen to start a wrapped line are not mistaken for subdivisions.
"""
import pathlib
import re

from common import norm, token_estimate

CEILING_TOKENS = 1500
STYLE_ORDER = ["lower", "digit", "upper", "roman", "ROMAN"]
ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv",
         "xvi", "xvii", "xviii", "xix", "xx"]
LABEL_RE = re.compile(r"^\(([A-Za-z]{1,3}|\d{1,3})\)(?=\s|$)\s*(.*)$", re.S)
# A wrapped line that merely starts with a citation, e.g. "(c) of this section", is not a label.
CONTINUATION_WORDS = {"of", "and", "or", "to", "for", "in", "on", "as", "at", "by", "than",
                      "through", "with", "above", "below", "shall", "above,", "is", "are"}
TOC_RE = re.compile(r"\.{5,}\s*\d+\s*$")
HEADER_RES = [re.compile(r"^Page \d+ of \d+$"), re.compile(r"^CPPA$")]


# ---------- label sequences ----------

def style_of(label: str, prev_style_hint: str | None = None) -> list[str]:
    """Possible styles for a label (roman letters are ambiguous with alphabetic ones)."""
    out = []
    if label.isdigit():
        return ["digit"]
    if label.islower():
        out.append("lower")
        if label in ROMAN:
            out.append("roman")
    elif label.isupper():
        out.append("upper")
        if label.lower() in ROMAN:
            out.append("ROMAN")
    return out


def lower_successors(label: str) -> set[str]:
    """After z comes aa; then either ab (spreadsheet style) or bb (doubled-letter style)."""
    if len(label) == 1:
        if label == "z":
            return {"aa"}
        return {chr(ord(label) + 1)}
    out = set()
    a, b = label[0], label[1]
    if a == b:  # doubled style: aa -> bb
        out.add(chr(ord(a) + 1) * 2)
    if b != "z":
        out.add(a + chr(ord(b) + 1))
    else:
        out.add(chr(ord(a) + 1) + "a")
    out.add(chr(ord(a) + 1) * 2)
    return out


def successors(style: str, label: str) -> set[str]:
    if style == "digit":
        return {str(int(label) + 1)}
    if style == "lower":
        return lower_successors(label)
    if style == "upper":
        return {s.upper() for s in lower_successors(label.lower())}
    if style == "roman":
        i = ROMAN.index(label) if label in ROMAN else -1
        return {ROMAN[i + 1]} if 0 <= i < len(ROMAN) - 1 else set()
    if style == "ROMAN":
        i = ROMAN.index(label.lower()) if label.lower() in ROMAN else -1
        return {ROMAN[i + 1].upper()} if 0 <= i < len(ROMAN) - 1 else set()
    return set()


def first_label(style: str) -> str:
    return {"lower": "a", "digit": "1", "upper": "A", "roman": "i", "ROMAN": "I"}[style]


# ---------- raw text extraction ----------

def raw_lines(path: pathlib.Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        import pymupdf
        doc = pymupdf.open(path)
        pages = [p.get_text() for p in doc]
    else:
        pages = [path.read_text(encoding="utf-8")]
    lines = []
    for text in pages:
        for ln in text.split("\n"):
            s = norm(ln)
            if not s or any(r.match(s) for r in HEADER_RES):
                continue
            lines.append(s)
    return lines


# ---------- tree ----------

class Node:
    def __init__(self, label, style, depth):
        self.label, self.style, self.depth = label, style, depth
        self.own: list[str] = []
        self.children: list["Node"] = []

    def own_text(self) -> str:
        return " ".join(self.own).strip()

    def render(self, indent=0) -> str:
        head = f"({self.label}) " if self.label else ""
        lines = ["  " * indent + (head + self.own_text()).strip()]
        for c in self.children:
            lines.append(c.render(indent + 1))
        return "\n".join(l for l in lines if l.strip())


def build_tree(lines: list[str]) -> list[Node]:
    """Return top-level nodes. Unlabelled leading text becomes a node with label ''."""
    top: list[Node] = []
    stack: list[Node] = []
    level1_style = None

    def place(label: str):
        """Decide where a label goes. Returns a placement tuple or None (then it is plain text)."""
        cands = style_of(label)
        if stack:  # 1) first child of the open node
            cur = stack[-1]
            if not cur.children and level1_style is not None:
                for st in cands:
                    if label == first_label(st) and                             STYLE_ORDER.index(st) == STYLE_ORDER.index(cur.style) + 1:
                        return ("child", st)
        if stack:  # 2) next sibling at any open level, deepest first
            for depth in range(len(stack) - 1, -1, -1):
                node = stack[depth]
                if node.label == "":
                    continue
                for st in cands:
                    if st == node.style and label in successors(st, node.label):
                        return ("sibling", depth, st)
        if not top and label in ("a", "1", "A", "i"):  # 3) first label of the section
            return ("first", {"a": "lower", "1": "digit", "A": "upper", "i": "roman"}[label])
        if top and top[0].label == "" and len(top) == 1 and not top[0].children:  # 4) after lead-in text
            for st in cands:
                if label == first_label(st):
                    return ("first", st)
        return None

    for ln in lines:
        pending = ln
        while pending:
            m = LABEL_RE.match(pending)
            if m and m.group(2)[:1].islower() and m.group(2).split(" ")[0] in CONTINUATION_WORDS:
                m = None
            placed = place(m.group(1)) if m else None
            if not placed:
                if not stack:
                    lead = Node("", "lead", 0)
                    top.append(lead)
                    stack = [lead]
                stack[-1].own.append(pending)
                break
            label, rest = m.group(1), m.group(2)
            if placed[0] == "first":
                node = Node(label, placed[1], 0)
                level1_style = placed[1]
                top.append(node)
                stack = [node]
            elif placed[0] == "child":
                node = Node(label, placed[1], len(stack))
                stack[-1].children.append(node)
                stack.append(node)
            else:
                _, depth, st = placed
                node = Node(label, st, depth)
                if depth == 0:
                    top.append(node)
                else:
                    stack[depth - 1].children.append(node)
                stack = stack[:depth] + [node]
            pending = rest      # the rest of the line may start with a nested label: "(ad) (1) ..."
    return top


def defined_term(text: str) -> str:
    """Quoted term(s) a definition begins with, e.g. '(ad) (1) "Sell," "selling," ... means' -> 'Sell; selling; ...'."""
    flat = norm(text)
    flat = re.sub(r"^(?:\([^)]{1,3}\)\s*)+", "", flat)
    if not re.match(r"^[“\"]", flat):
        return ""
    head = flat.split(" means")[0] if " means" in flat else flat[:200]
    terms = re.findall(r"[“\"]([^”’\"]+)[”’\"]+", head)
    return "; ".join(t.strip(" ,.;") for t in terms if t.strip(" ,.;"))


# ---------- main parse ----------

SMALL = {"of", "to", "and", "the", "for", "in", "a", "an", "or", "on", "with"}


def pretty_article(label: str) -> str:
    """'ARTICLE 2.  REQUIRED DISCLOSURES TO CONSUMERS' -> 'Article 2. Required Disclosures to Consumers'."""
    if not label:
        return ""
    words = norm(label).lower().split(" ")
    out = [w if (i and w in SMALL) else w.capitalize() for i, w in enumerate(words)]
    return " ".join(out)


def clean_toc_title(parts: list[str]) -> str:
    t = " ".join(parts)
    t = re.sub(r"\.{3,}\s*\d*\s*$", "", t)           # dotted leader + page number
    t = re.sub(r"\s*\.{3,}.*$", "", t)
    return norm(t)


def read_toc(lines: list[str], head, art):
    """Table of contents = heading-like lines until the first number repeats (the body starts there)."""
    entries, seen, body_start = [], set(), len(lines)
    i = 0
    while i < len(lines):
        hm = head.match(lines[i])
        if hm:
            num = hm.group(1)
            if num in seen:
                body_start = i
                break
            seen.add(num)
            parts = [hm.group(2)]
            j = i + 1
            while j < len(lines) and not head.match(lines[j]) and not (art and art.match(lines[j])):
                parts.append(lines[j])
                j += 1
            entries.append((num, clean_toc_title(parts)))
            i = j
            continue
        i += 1
    return entries, body_start


def split_sections(lines: list[str], profile: dict):
    """Return ([{num, title, lines, article}], toc_numbers). The TOC is the ordered whitelist of sections."""
    head = re.compile(profile["heading_re"])
    art = re.compile(profile["article_re"]) if profile.get("article_re") else None
    if profile.get("toc"):          # sources without a printed table of contents list their sections
        toc, start = [(n, "") for n in profile["toc"]], 0
    else:
        toc, start = read_toc(lines, head, art)
    toc_titles = dict(toc)
    expected = [n for n, _ in toc]
    sections, cur, ei = [], None, 0
    article, in_article_title = profile.get("default_article", ""), False
    i = start
    if art and start > 0 and art.match(lines[start - 1]):
        i = start - 1   # the first ARTICLE heading sits just before the first section
    while i < len(lines):
        ln = lines[i]
        i += 1
        if art and art.match(ln):
            article, in_article_title, cur = norm(ln), True, None
            continue
        hm = head.match(ln)
        if hm and ei < len(expected) and hm.group(1) == expected[ei]:
            full = toc_titles.get(hm.group(1), "")
            title = norm(hm.group(2))
            # a wrapped title continues on the following lines until it equals the TOC title
            while full and len(title) < len(full) and i < len(lines) and                     norm(full).startswith(norm(title + " " + lines[i])[:len(norm(title + " " + lines[i]))]):
                title = norm(title + " " + lines[i])
                i += 1
            cur = {"num": hm.group(1), "title": full or title, "lines": [], "article": article}
            sections.append(cur)
            ei += 1
            in_article_title = False
            continue
        if in_article_title and ln.upper() == ln:   # wrapped, all-caps article title
            article += " " + ln
            continue
        in_article_title = False
        if cur is not None:
            cur["lines"].append(ln)
    return sections, expected


def parse(path: pathlib.Path, doc: dict, retrieved_at: str) -> tuple[list[dict], list[str]]:
    profile = doc["profile"]
    doc_id = doc["doc_id"]
    short = doc["short_name"]
    sym = profile.get("symbol", "§")
    lines = raw_lines(path)
    sections, toc = split_sections(lines, profile)
    chunks: list[dict] = []
    defs_sections = set(profile.get("definition_sections", []))

    def mk(cid, kind, ref, heading, text, hier, parent, number, permalink, **extra):
        c = {"chunk_id": cid, "doc_id": doc_id, "kind": kind, "number": number, "hierarchy": hier,
             "section_ref": ref, "heading": heading, "text": text, "parent_chunk_id": parent,
             "token_count": token_estimate(text), "footnotes": [], "topics": [],
             "jurisdiction": doc["jurisdiction"], "doc_type": doc["doc_type"],
             "source_url": doc["source_url"], "retrieved_at": retrieved_at, "permalink": permalink}
        c.update(extra)
        return c

    for sec in sections:
        num, title = sec["num"], sec["title"].rstrip(".").strip()
        title = title or profile.get("default_title", "")
        if profile.get("article_re"):
            sec["article"] = pretty_article(sec["article"])
        body, note = [], []
        in_note = False
        note_re = re.compile(profile.get("note_re", r"^Note:"))
        for ln in sec["lines"]:
            if note_re.match(ln):
                in_note = True
            (note if in_note else body).append(ln)
        # heading continuation: a wrapped title shows up as an unlabelled first line in lowercase/Title Case
        tree = build_tree(body)
        sec_id = f"{doc_id}:sec:{num}"
        base_hier = ([sec["article"]] if sec["article"] else []) + [f"Section {num}"]
        sec_ref = f"{short} {sym} {num}"
        permalink = f"{doc_id}/sec/{num}/"
        children = []

        def emit(node, path, lead_in="", top_level=False):
            label_path = ".".join(path)
            cid = f"{sec_id}:{label_path}" if label_path else f"{sec_id}:0"
            text = node.render()
            ref = sec_ref + "".join(f"({p})" for p in path)
            frag = "p" + label_path if label_path else ""
            kind, term = "paragraph", ""
            if num in defs_sections and len(path) == 1:
                term = defined_term(text)
                kind = "definition"
            hier = base_hier + ([f"Subdivision ({path[0]})"] if path else []) + \
                   [f"({p})" for p in path[1:]]
            heading = f"Definition: {term}" if term else title
            c = mk(cid, kind, ref, heading, text, hier, sec_id, label_path or "0",
                   permalink + (f"#{frag}" if frag else ""),
                   **({"defined_term": term} if term else {}),
                   **({"lead_in": lead_in} if lead_in else {}))
            children.append(c)

        def walk(node, path, lead_in=""):
            text = node.render()
            if token_estimate(text) > CEILING_TOKENS and node.children and kind_splittable(node):
                own = (f"({node.label}) " if node.label else "") + node.own_text()
                for ch in node.children:
                    walk(ch, path + [ch.label], (lead_in + " " + own).strip() if lead_in else own)
            else:
                emit(node, path, lead_in)

        def kind_splittable(node):
            return True

        if not tree:
            continue
        if len(tree) == 1 and tree[0].label == "":
            emit(tree[0], [])
        else:
            for node in tree:
                if node.label == "":
                    # unlabelled lead-in before (a): attach as its own chunk
                    emit(node, [])
                else:
                    walk(node, [node.label])
        full = "\n".join(c["text"] for c in children)
        parent = mk(sec_id, "section", sec_ref, title, full, base_hier, None, num, permalink,
                    child_chunk_ids=[c["chunk_id"] for c in children])
        if note:
            parent["note"] = " ".join(note)
        chunks.append(parent)
        chunks.extend(children)
    return chunks, toc
