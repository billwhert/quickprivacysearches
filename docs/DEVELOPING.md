# Developing

## Layout
- `sources.yaml` - every document: URL, type, jurisdiction, parser, expected counts
- `synonyms.yaml` - query expansion terms (used from build step 4)
- `topics/` - guided topic YAML files (build step 9)
- `data/raw/` - original source files, untouched, with `manifest.json` (URL, checksum, retrieval date)
- `data/processed/<doc_id>/` - `document.json`, `chunks.json`, `crossrefs.json`
- `data/reports/<doc_id>_validation.md` - validation checks and a 10-chunk spot-check
- `build/` - ingestion pipeline (`ingest.py`, `parse_eurlex.py` for EU acts, `parse_code.py` for
  US statutes and regulations in PDF or text, `validate*.py`) and site generator (`pages.py`)
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

## How search works
All of it runs in the browser (`web/assets/lookup.js`, shared with the test runner):
1. **Citation lookup** - "Art. 35(1)", "Recital 26" jump straight to the provision.
2. **Cleanup** - stopwords removed, light stemming ("bases" and "base" match).
3. **Jurisdiction detection** - words like "GDPR" filter to a law; a law that is not loaded
   yet (for example "Canada") gets a clear "not loaded yet" message instead of unrelated text.
4. **Synonym expansion** - `synonyms.yaml`; expansions are searched at 70% weight and shown
   to the visitor as "also searched".
5. **Ranking** - term, heading and citation boosts; multi-word phrase matches rank higher;
   paragraph 1 gets a small tie-breaker bonus.

To add or fix a synonym, edit `synonyms.yaml` and rebuild. `node tests/run_queries.mjs` shows
what changed; set `VERBOSE=1` to see the top results for every query.

## Adding a US statute or regulation
Documents with `parser: code` in `sources.yaml` use `build/parse_code.py`. Each entry needs a
`profile` with a `heading_re` (matches section headings and captures the number and title).
Optional profile keys: `article_re` (article/chapter headings), `definition_sections`
(sections chunked per defined term), `toc` (explicit section list when the source has no
printed table of contents), `note_re` (history/authority lines kept apart from the text).
The parser uses the document's own table of contents as the ordered list of sections, so a
citation that happens to start a wrapped line is never mistaken for a heading.

Sources that block scripted downloads (the California Legislature's leginfo site does) can use
`fetch_method: manual`: save the text under `data/raw/` and describe how it was captured in
`fetch_note`. The manifest records the checksum and capture date.

## Federal regulations from the eCFR
Documents with `parser: ecfr` list their `parts` in `sources.yaml`. `build/fetch_ecfr.py` saves,
for each part, the eCFR renderer HTML and the official structure JSON (the table of contents),
all from one resolved date. `build/parse_ecfr.py` nests paragraphs by eCFR's indent levels and
labels them from the paragraph ids, and validation checks the parsed sections against the
official structure list. Each result links to the section on ecfr.gov.

## Filters, browsing and permalinks (step 7)
- **Filters:** `docsForFilters()` in `lookup.js` turns the filter bar (law, type, jurisdiction;
  OR within a group, AND across groups) into a document list that `search()` takes as
  `opts.docs`. Filters live in memory only, so a refresh clears them. The topic filter arrives
  with topic tagging (step 8).
- **Browse:** `/documents/` lists every loaded law with its version and retrieval date. Each law's
  contents page has a "Find a section" box that also searches paragraph headings and defined terms.
- **Permalinks:** every provision page has a stable URL, `#p...` anchors for subdivisions, and a
  "Copy link" button; search results have one too. Search queries are never part of a link.
