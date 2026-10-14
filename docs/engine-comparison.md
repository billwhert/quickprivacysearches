# Search engine comparison (build step 3)

Compared on 18 GDPR queries (3 spec tests + 15 extras). A query "hits" if an expected
provision is in the top 3. Both engines received the same cleaned query (stopwords removed);
MiniSearch used term/heading/reference boosts, Pagefind used heading weights.

| Engine | Hits (cleaned query) | Hits (raw question) |
|---|---|---|
| MiniSearch (OR + prefix + fuzzy 0.15) | 15 / 18 | not run |
| MiniSearch (AND) | 13 / 18 | not run |
| Pagefind 1.5.2 | 14 / 18 | 9 / 18 |

Findings
- Pagefind requires all query words to match, so long questions often return nothing
  (e.g. "deadline respond data subject access request", "contract between controller processor contain").
- MiniSearch's OR ranking returns the best partial matches, which suits natural-language questions.
- Both missed "DPIA" (abbreviation not in the text) and "erase my data" (different wording):
  these are synonym problems for step 4, not engine problems.
- Size at GDPR scale: MiniSearch index built in the browser from `search-data.json` (~570 KB raw,
  well under 200 KB gzipped, the page index adds ~80 KB library). Pagefind output was ~3 MB
  including its UI files, split into on-demand pieces.
- Pagefind scales better for very large corpora; revisit if the combined phase 1 data
  makes the initial download too large (measure after step 6).

Decision: MiniSearch. Pagefind removed from the build.
