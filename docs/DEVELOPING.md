# Developing

## Layout
- `sources.yaml` - every document: URL, type, jurisdiction, parser, expected counts
- `synonyms.yaml` - query expansion terms (used from build step 4)
- `topics/` - guided topic YAML files (build step 9)
- `data/raw/` - original source files, untouched, with `manifest.json` (URL, checksum, retrieval date)
- `data/processed/<doc_id>/` - `document.json`, `chunks.json`, `crossrefs.json`
- `data/reports/<doc_id>_validation.md` - validation checks and a 10-chunk spot-check
- `build/` - ingestion pipeline (`ingest.py`, `parse_*.py`, `validate.py`) and site generator (`pages.py`)
- `web/assets/` - search page JavaScript and CSS; `lookup.js` holds citation lookup and query cleanup
- `web/vendor/minisearch.js` - vendored search library (MIT)
- `tests/run_queries.mjs` - acceptance queries run against the built site
- `docs/engine-comparison.md` - why MiniSearch was chosen over Pagefind

## Setup
Python 3.11 to 3.13 (PyYAML has no prebuilt wheel for 3.15 yet) and Node 20+.

```bash
python -m pip install -r requirements.txt
npm install
```

## Ingest a document
```bash
python build/ingest.py gdpr                 # fetch (skipped if raw file exists) -> parse -> validate
python build/ingest.py gdpr --force-fetch   # re-download and compare checksums
```

## Build and test the site
```bash
python build/build.py                       # writes dist/
python -m http.server -d dist 8000          # open http://localhost:8000
node tests/run_queries.mjs                  # acceptance queries against dist/
```

## Deploy
Pushing to `main` runs `.github/workflows/pages.yml`, which builds the site and
publishes it to GitHub Pages. The workflow only needs Python; processed data is committed.

## Pages limits
As last known: site up to about 1 GB, about 100 GB/month soft bandwidth, 100 MB per file.
Verify at https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
