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
| F-32 | P3 | Legal | The disclaimer and privacy notice are plain-language drafts. Consider a lawyer's review before wide promotion. | step 11 |
| F-34 | P3 | Content | **Paused by owner decision.** Remaining Phase 2 candidates, if ever wanted: LGPD (Portuguese original; English would be an unofficial translation), Virginia/Colorado/Texas statutes (state legislature sites often block scripted downloads), and guidance (EDPB/WP29, ICO, NIST), which must look visibly different from binding law. | step 13 |
| F-35 | P3 | Decision | Step 14 (in-browser semantic search) is not recommended yet: 96 of 97 test queries pass with keywords and synonyms, and it would add a download of tens of MB. Revisit when real-use misses accumulate (see F-08). | step 14 |
| F-36 | P3 | Content | GLBA: the statute itself (15 U.S.C. 6801 et seq.) and the FTC's own Privacy Rule for motor vehicle dealers (16 CFR 313) are not loaded. | step 13 |
| F-37 | P2 | Search | Unseen-question review (84 questions, `tests/review/batch1.txt`): about 70 good first or second results. Still weak: "consent to send marketing emails" (surfaces HIPAA fundraising, no GDPR consent/ePrivacy hit), "what must a financial privacy notice say" (should lead with 16 CFR 1016.6(a)), "what is nonpublic personal information" (314.2(l) ranks second), "can a business refuse a deletion request" (GDPR before CCPA 1798.105(d)), "ten privacy principles in Canada" (lands on 4.5.x, not the principle list), "can an employer collect employee information". | search review |
| F-33 | P3 | Review | Real-device check of the new design (phone and a large monitor) is still outstanding; emulated phone width shows no overflow on 11 page types. | review |
| F-04 | P2 | Launch | Open the live site on a real phone using mobile data (not Wi-Fi) and try three searches. Everything else in the launch checklist was verified (see `docs/ACCEPTANCE.md`); a real device on a different network is the one thing I cannot do from here. | step 12 |
| F-05 | P2 | Content | The two guided topics are published as a **first-release approval**; the line-by-line review of their provision lists is still pending. When you have time: `data/reports/guided_topics_review.md` (long; the review sheet lists every provision with its full text). The pages say "line-by-line review pending" until you re-approve with your own wording. | step 9 |
| F-26 | P2 | Content | Eight comparison sets (`compare/*.yaml`) are an editorial selection of provisions and have not been reviewed. The page says they are not a statement of equivalence. Check the columns make sense; add or remove provisions in the YAML. | step 10 |
| F-27 | P3 | Feature | Compare view could be linked from guided topics and from search results that span several laws. | step 10 |
| F-24 | P2 | Content | Guided topics have no hand-written summaries yet (only short applicability notes). The spec allows summaries only after you have written or reviewed them. | step 9 |
| F-25 | P3 | Content | More guided topics for the other loaded laws (GDPR DPIA, DSAR handling, HIPAA breach notification) once the first two are approved. | step 9 |
| F-06 | P2 | Search | "how to verify a consumer request": the verification regulations (7060-7063) rank 5th behind a definition and other request rules. | step 5 |
| F-07 | P2 | Search | "how long must documentation be retained" does not surface HIPAA 164.530(j) (documentation, 6 years). | step 6 |
| F-08 | P2 | Search | Synonym vocabulary gaps keep appearing on new, unseen questions (about 1 in 4 on held-out checks). Keep a list of failed real queries and add them as regression tests. | step 5-7 |
| F-09 | P2 | UI | With a law filter on, the "Also searched related wording" line can still show expansions from other laws (for example GDPR terms when filtered to HIPAA). Harmless to results but noisy. | step 7 |
| F-10 | P2 | UI | Filter counts are capped by the top-150 candidate list and shown as "99+". Could show exact counts. | step 7 |
| F-11 | P2 | Data | GDPR text is the Official Journal original as published. Corrigenda (2018) may not be reflected; consider using the consolidated text and recording the version. | step 2 |
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

### Search-quality pass on unseen questions (2026-10-14)
- Ran 84 untuned, realistic questions across all six laws (`node tests/review_queries.mjs tests/review/batch1.txt 3`) and judged results by eye.
- Fixed: the bare "how long" synonym group hijacked retention questions (narrowed to response-time phrasing; added retention, records-of-requests, DPA, update-frequency, charge/retaliation, encryption, FTC notification, notice-contents, ten-principles, enforcement and family groups); generic "email"/"text" no longer pull in HIPAA texting rules.
- Ranking: "what is X" now acts like a definition request; procedural questions ("how do we", "when must") penalise definitions harder; "what must be in" questions lightly favour provisions that list required content; collection/objection-style words stem together.
- Added law cues: patient, bank, FTC, Privacy Commissioner. Existing suites unchanged (106/107, gold 66/66). Remaining weak cases are logged as F-37.

### Step 13 - PIPEDA added; further coverage paused (2026-10-14)
- Added PIPEDA (S.C. 2000, c. 5) from the Department of Justice's official XML: 84 of 84 sections (71 body sections, the ten
  principles of Schedule 1 as sections, and Schedules 2-4), 341 chunks, all validation checks pass. New parser `build/parse_justice.py`.
- Reuse terms confirmed from the Reproduction of Federal Law Order (SI/97-5): free reproduction without permission if accuracy is
  checked and it is not presented as the official version.
- Added PIPEDA citations (`PIPEDA s. 10.1`, `PIPEDA clause 4.3.1`), vocabulary, 7 comparison columns, 9 tests and 5 topic-gold provisions.
- Spec test 17's out-of-scope example moved from Canada (now loaded) to Brazil.
- Owner decision: no further documents for now; the site itself needs checking and tuning first (see F-34).

### Step 13 - GLBA (2026-10-14)
- Added the FTC Safeguards Rule (16 CFR Part 314) and Regulation P (12 CFR Part 1016) from the eCFR: 24 of 24 sections match
  the official structure list, all validation checks pass, 148 chunks.
- Pipeline generalized: an eCFR document may combine parts from different CFR titles; sections outside any subpart are handled;
  appendices of running text are split at paragraph boundaries; cross-reference patterns are per document.
- Added GLBA vocabulary, three comparison columns (breach notification, privacy notices, vendor oversight), 10 search tests and
  5 topic-gold provisions.
- Review polish: guided-topic and compare provision cards restructured (citation first, clamped text, footer links), topic
  headers show steps/provisions/laws, Sources has a jump row. All 11 page types fit a 375px phone.

### Review and redesign pass (2026-10-14)
Found and fixed by a full review of the code, the built site and the saved texts:
- **485 broken links** on the four law contents pages (section lists, "Start reading", recitals grid) - all links were missing
  the `../` prefix. Present since step 5. New `tests/check_links.py` resolves every link and anchor on every page (0 broken now).
- **27 provisions** stored words split across a PDF line break with a stray space ("opt- in", "toll- free"). Fixed in the parser.
- The Back button wiped a search; refresh still clears it (by design), Back no longer does.
- Highlighting matched fragments inside unrelated words; it now matches at word starts.
- The "not loaded yet" message printed internal ids (for example "CCPA_REGS"); `topics.json` could be served stale; the HIPAA
  appendix table printed empty cells.
Redesign: new look and layout across the site (hero search, filters in a panel with removable pills, calmer result cards with a
"more" menu, clamped long text, footer columns, sticky section navigation, guided-topic steps, compare columns).
Added: provision cards on guided-topic and compare pages show the citation first, clamp long text, and keep links in a footer.

### Step 12 - Launch (2026-10-14)
- Owner decisions applied: MIT license added for the code and editorial files; **CalOPPA removed entirely** (its source site
  cautions about copyright); About page simplified and the maintainer/AI-assistance wording removed.
- Scope change: phase 1 is now GDPR, CCPA/CPRA, CPPA regulations and HIPAA. CalOPPA is no longer loaded; searches that name it say it
  is not loaded. The two guided topics and the privacy-notice comparison were trimmed to match and re-approved.
- Verified live: no request carries search text and nothing but this site is contacted (spec test 20); no horizontal overflow at
  375px on 11 page types (the header nav was overflowing and now wraps); repository public with MIT detected; HTTP redirects to HTTPS.
- Added share metadata (description and Open Graph tags), a friendly 404 page and a sitemap.
- Acceptance record: `docs/ACCEPTANCE.md`.

### Step 11 - Trust pages (2026-10-14)
- Added About, Disclaimer and privacy notice, and Sources pages, linked from every page's footer.
- Confirmed reuse terms from the publishers' own pages: EUR-Lex (Decision 2011/833/EU, source acknowledged), State of California Conditions of Use (public domain unless indicated), eCFR/OFR (US Government work; editorial compilation, not official), California Legislature (notes possible copyright; see F-29). Attribution text is shown on Sources.
- Added a GitHub issue form ("Report an error") with links on every provision page and result, prefilled with the provision and page address only, never a search.
- Added `tests/check_site.py`, which verifies the privacy claims (no third-party resources, cookies, storage or tracking) and that every document has attribution and reuse links.

### Step 10 - Compare view (2026-10-14)
- Added `/compare/` with eight hand-written comparison sets (request deadlines, breach notification, access, deletion, definitions of personal data, privacy notices, penalties, processor contracts).
- Each set is a YAML file; text comes from the stored provisions; the build fails if a cited provision is missing or sits in the wrong column's document. Columns can be hidden with law toggles.
- Both guided topics were approved for first release (see F-05).

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
