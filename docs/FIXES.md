# Fixes, updates and open items

One place to see what changed and what still needs doing. Newest entries go at the top of
each section. `P1` = matters for launch, `P2` = should do, `P3` = nice to have.

How to use this file
- New problem or idea: add a row to **Open items** with the next ID.
- Fixed or shipped: move it to **Change log** (keep the ID) with the date and build step.

## Open items

| ID | Pri | Area | Item | Found in |
|---|---|---|---|---|
| F-01 | P1 | Review | `synonyms.yaml` (about 70 groups) was drafted by the assistant. The spec says curated lists must be reviewed by you. Review for wrong or over-broad mappings. | step 4-6 |
| F-02 | P1 | Review | Topic tags (step 8) are keyword-assigned first pass. Review `data/reports/topic_review.csv` and record corrections in `taxonomy/overrides.yaml`. | step 8 |
| F-22 | P2 | Topics | First-pass tags are noisiest for `security-safeguards` (about 190 provisions, mostly GDPR, from words like "safeguards") and `data-subject-rights` / `right-opt-out` in the CCPA regulations (most of that document is about requests). Review and tighten phrases in `taxonomy/topics.yaml` after looking at the "Phrases doing the work" table in `data/reports/topic_tagging.md`. | step 8 |
| F-23 | P3 | Topics | About 30% of provisions have no topic (mostly institutional or procedural: supervisory authority duties, agency staffing, hearings). That is expected; add topics via `taxonomy/overrides.yaml` only where one clearly fits. | step 8 |
| F-03 | P1 | Legal | License and attribution wording for every source is a placeholder (EU reuse decision, CPPA, California Legislature, eCFR). Confirm and display on Sources page. | step 11 |
| F-04 | P1 | Launch | Spec test 20: confirm in a browser's network tab that query text is never sent anywhere. Also test on a phone and a different network. | step 12 |
| F-05 | P1 | Content | **Review the two guided topics and publish them.** Open `data/reports/guided_topics_review.md`, check every cited provision, edit `topics/*.yaml` if needed, then run `python build/guided.py approve <id> --by "Your name"`. Until then they are hidden on the live site. | step 9 |
| F-24 | P2 | Content | Guided topics have no hand-written summaries yet (only short applicability notes). The spec allows summaries only after you have written or reviewed them. | step 9 |
| F-25 | P3 | Content | More guided topics for the other loaded laws (GDPR DPIA, DSAR handling, HIPAA breach notification) once the first two are approved. | step 9 |
| F-06 | P2 | Search | "how to verify a consumer request": the verification regulations (7060-7063) rank 5th behind a definition and other request rules. | step 5 |
| F-07 | P2 | Search | "how long must documentation be retained" does not surface HIPAA 164.530(j) (documentation, 6 years). | step 6 |
| F-08 | P2 | Search | Synonym vocabulary gaps keep appearing on new, unseen questions (about 1 in 4 on held-out checks). Keep a list of failed real queries and add them as regression tests. | step 5-7 |
| F-09 | P2 | UI | With a law filter on, the "Also searched related wording" line can still show expansions from other laws (for example GDPR terms when filtered to HIPAA). Harmless to results but noisy. | step 7 |
| F-10 | P2 | UI | Filter counts are capped by the top-150 candidate list and shown as "99+". Could show exact counts. | step 7 |
| F-11 | P2 | Data | GDPR text is the Official Journal original as published. Corrigenda (2018) may not be reflected; consider using the consolidated text and recording the version. | step 2 |
| F-12 | P2 | Data | CalOPPA raw text was captured by hand from the rendered leginfo page (leginfo blocks scripted downloads), so it is not a byte-exact download. Re-capture when leginfo allows scripted access, or note in Sources. | step 5 |
| F-13 | P2 | Data | CCPA statute and regulations come from the CPPA's consolidated PDFs, not the Legislature's leginfo or OAL. Fine for now; state this clearly on the Sources page. | step 5 |
| F-14 | P2 | Data | eCFR is an editorial compilation, not the official annual CFR. Say so on the Sources page. | step 6 |
| F-15 | P2 | Feature | Export a set of results to Markdown / print-friendly (spec section 11) is not built. | planned |
| F-16 | P2 | Ops | GitHub Pages limits (size, bandwidth) are from memory. Verify the current numbers and monitor `search-data.json` (about 320 KB gzipped now; grows with every law). | step 1, 6 |
| F-17 | P2 | Ops | Add `.gitattributes` text normalization to stop the LF/CRLF warnings on every commit. | step 3 |
| F-18 | P3 | Data | Some CCPA sections (1798.136, .146, .148, most of 1798.199.x) have no title in the CPPA PDF, so they show only the citation. | step 5 |
| F-19 | P3 | Data | GDPR recitals are not linked to the articles they relate to (the source does not say). Could be added as manual links. | step 2 |
| F-20 | P3 | Dev | Local default Python is 3.15, which cannot build PyYAML; builds use 3.12. Document or install a 3.12 default. | step 1 |
| F-21 | P3 | CI | GitHub Actions warns that `ubuntu-latest` moves to Ubuntu 26 on 2026-10-19. Re-run the workflow after that date and bump action versions if needed. | step 7 |

## Change log

### Step 9 - Guided topics (2026-10-14)
- Engine: topics are YAML files in `topics/`; text is always pulled from the stored provision; build fails if a cited provision does not exist; wording that tells the reader what to do is rejected.
- Two draft topics: California business privacy notice; Cookies and tracking (California). Spec tests 14, 15, 16 pass.
- Draft/published lifecycle with `approve` command, change fingerprints and a "needs review" flag, plus a generated review sheet.
- Search shows topic cards above results; home page features published topics; new Guides page.
- Fixed while building: side-nav labels on topic pages were cut mid-word (now wrap).

### Step 8 - Topic tagging (2026-10-14)
- 16 topics plus 5 sub-topics of individual rights; every ingest re-applies the rules and your overrides.
- Gold check `tests/check_topics.py`: 57 provisions with known topics. Note the rules were tuned against this set, so treat it as a regression guard, not an accuracy score.
- Tightened rules after the rule-hit table showed `inform*` (354 hits), `disclos*` (243) and "protected health information" (tagged nearly all of HIPAA as sensitive).
- Added the controlled vocabulary and first-pass keyword tagging (`taxonomy/topics.yaml`).
- Added manual corrections that survive rebuilds (`taxonomy/overrides.yaml`).
- Added the reviewable file `data/reports/topic_review.csv` and a coverage report.
- Added the topic filter and topic tags on results and provision pages.

### Step 7 - Filters, Browse, permalinks (2026-10-14)
- Search filters for law, type and jurisdiction, with per-law match counts.
- New Browse page; each law has a "Find a section" box and a "Start reading" link.
- "Copy link" buttons on every provision and search result.
- Finder also searches paragraph headings and defined terms.

### Step 6 - HIPAA (2026-10-14)
- Ingested 45 CFR Parts 160 and 164 from the eCFR (102 sections, validated against the official structure list).
- Fixed: eCFR mislabels one id (Business associate item) - nesting now follows indent levels.
- Fixed: "covered entity" and "business associate" were stripped from questions as law-identifying words.
- Added: comparison questions ("GDPR vs. HIPAA") show both laws; exact defined-term boost; paragraph headings indexed as a boosted field.

### Step 5 - CCPA, CPPA regulations, CalOPPA (2026-10-14)
- Ingested all three; validated against each document's own table of contents.
- Fixed: a wrapped line starting with a citation such as "(c), and ..." was read as a subdivision label.
- Fixed: legal labels were displayed in capitals ("(A)" for "(a)").
- Added: rarity weighting of query terms, quoted defined-term boost, operative rules ranked above definitions, best-match-per-law for neutral questions.

### Step 4 - Synonyms and query handling (2026-10-14)
- Synonym expansion, light stemmer, phrase and first-paragraph boosts, jurisdiction detection with a clear "not loaded yet" message.

### Interim fixes (2026-10-14)
- Refreshing the page now always gives a blank search (searches are no longer kept in the URL; old `#q=` links are dropped).
- Stylesheet and script URLs carry a version stamp so browsers pick up changes immediately.
- Layout scales on large monitors and collapses cleanly on phones.
- README rewritten for visitors; developer notes moved to `docs/DEVELOPING.md`.

### Step 3 - Static search (2026-10-14)
- Compared MiniSearch and Pagefind (see `docs/engine-comparison.md`); kept MiniSearch.

### Step 2 - GDPR (2026-10-14)
- Ingested the GDPR (99 articles, 173 recitals, 26 definitions), validated end to end.
- Fixed: nested lettered points were emitted twice; footnote markers left a stray space.

### Step 1 - Skeleton (2026-10-14)
- Repository, GitHub Pages deployment, `sources.yaml`.
