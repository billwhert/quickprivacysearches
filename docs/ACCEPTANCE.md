# Acceptance record (launch, 2026-10-14)

How the build measures up against the spec's 20 test queries and its definition of done.
Re-run the search tests any time with `node tests/run_queries.mjs` (after `python build/build.py`).

## The 20 test queries

| # | Query | Result | Note |
|---|---|---|---|
| 1 | "GDPR Article 30" | Pass | Records of processing, Art. 30(1) |
| 2 | "1798.105" | Pass | Right to delete, 1798.105(a) |
| 3 | "164.502(b)" | Pass | Minimum necessary |
| 4 | When is a DPIA required under GDPR? | Pass | Art. 35(1) via the DPIA synonym |
| 5 | What must a record of processing activities contain? | Pass | Art. 30(1) |
| 6 | Exceptions to the CCPA right to delete | Pass | 1798.105(d) |
| 7 | HIPAA minimum necessary standard | Pass | 164.502(b) |
| 8 | Deadline to respond to a DSAR under GDPR | Pass, with a caveat | The right-of-access provisions (Art. 15) rank in the top 3; Art. 12(3), which contains the one-month deadline, is not always there |
| 9 | How does CCPA define "sell" and "share"? | Pass | Both definitions in the top 5 |
| 10 | Breach notification timelines, GDPR vs. HIPAA | Pass | Art. 33(1) and HIPAA 164.404/.408/.410 both appear |
| 11 | What counts as a "business associate" under HIPAA? | Pass | 160.103 definition first |
| 12 | Lawful bases for processing under GDPR | Pass | Art. 6(1) |
| 13 | What must a CCPA privacy notice include? | Pass | 1798.130(a)(5), 1798.100(a), regulations 7011 and 7012 |
| 14 | Long California privacy-notice-and-cookies question | Pass | Both guided topic cards at the top |
| 15 | Do I need a Do Not Sell link | Pass | Cookies and tracking topic |
| 16 | Does CCPA apply to my small business | Pass | 1798.140(d) in the top 3 and the privacy notice topic |
| 17 | A law outside the loaded sources (re-checked with Brazil's breach threshold, since Canada's PIPEDA is now loaded) | Pass | "not in the loaded sources yet", no invented text |
| 18 | "erase my data" | Pass | Art. 17 via synonyms |
| 19 | Filter to HIPAA only | Pass | Every result is HIPAA |
| 20 | No network calls with the query | Pass | Checked on the live site in a real browser: 9 requests on load, all to billwhert.github.io; none after searching; the query is not in any URL, the address bar, storage or cookies |

20 of 20 pass; one (8) carries the caveat above.

Beyond the spec, the repository's own suites also pass: 51 of 52 extra queries (one known ranking miss, F-06),
11 of 11 filter tests, 5 of 5 guided-topic tests, 56 of 56 topic gold provisions, and the 17 site checks in
`tests/check_site.py` that back up the privacy claims.

## Definition of done

| Item | Status |
|---|---|
| All phase 1 documents built with passing validation | **4 of 5.** GDPR, CCPA/CPRA, CPPA regulations and HIPAA pass every validation check. CalOPPA was removed at the owner's request (copyright caution on its source site). |
| At least 18 of 20 test queries pass; failures documented | Met (20 of 20) |
| Both initial guided topics reviewed and published | Published as a first-release approval; line-by-line review pending (F-05) |
| Every result shows citation, exact text, official link, version, retrieval date | Met |
| Public URL works on desktop and mobile with no login | Met (desktop; phone width emulated, no overflow on 11 page types). A real phone on mobile data is still worth one look (F-04). |
| Disclaimer, About, Sources and privacy notice live | Met |
| No query text sent to any server | Met (verified live) |
| Source licensing confirmed and attributions displayed | Met for the four loaded sources |
| A new document can be added by editing `sources.yaml` and, if needed, one parser | Met (see `docs/DEVELOPING.md`) |
| A push to GitHub rebuilds and redeploys automatically | Met |
