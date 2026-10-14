"""Minimal static build: reads sources.yaml and writes dist/index.html."""
import html
import pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def main() -> None:
    docs = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["documents"]
    rows = "\n".join(
        f"<li><strong>{html.escape(d['title'])}</strong> "
        f"({html.escape(d['doc_type'])}, {html.escape(d['jurisdiction'])}) - "
        f"<a href=\"{html.escape(d['source_url'])}\">official source</a></li>"
        for d in docs
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Law Reference Tool</title></head>
<body style="font-family:system-ui;max-width:42rem;margin:2rem auto;padding:0 1rem">
<h1>Privacy Law Reference Tool</h1>
<p>Hello. This is the hosting proof page. Search is not built yet.</p>
<h2>Planned phase 1 documents</h2>
<ul>
{rows}
</ul>
<p><em>Reference tool, not legal advice.</em></p>
</body></html>
"""
    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(page, encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote {DIST / 'index.html'} ({len(docs)} documents)")


if __name__ == "__main__":
    main()
