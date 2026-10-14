# Topic tagging

Every provision carries zero or more topics from a fixed list. Tags drive the **Topic** filter on
the search page and the small tags on results and provision pages.

## Where things are
| File | What it is | You edit it? |
|---|---|---|
| `taxonomy/topics.yaml` | The topic list and the keyword rules that assign topics | Yes |
| `taxonomy/overrides.yaml` | Your corrections; applied on every rebuild | Yes |
| `data/reports/topic_review.csv` | Every provision, its tags, which rules fired, and an excerpt | No (generated) |
| `data/reports/topic_tagging.md` | Coverage, counts per topic, the phrases doing the work, stale overrides | No (generated) |
| `tests/topic_gold.yaml` | Provisions whose topics are known to be right | Yes, as you confirm more |

## How a tag is decided
A provision scores points for each phrase found: more for a hit in its heading or defined term, less
in its text. A topic is assigned when the score reaches that topic's `min_score`. A sub-topic (for
example "Deletion / erasure") also assigns its parent ("Individual rights"). Every defined term gets
"Definitions". Details are at the top of `taxonomy/topics.yaml`.

## Reviewing and correcting
1. Run `python build/tag_topics.py` (also runs automatically on every ingest).
2. Open `data/reports/topic_review.csv` in a spreadsheet. Filter on a topic or a document.
3. For a wrong or missing tag, add an entry to `taxonomy/overrides.yaml`:
   ```yaml
   overrides:
     - id: gdpr:art:23:1          # a provision, or a whole section/article id
       add: [exemptions]
       remove: [security-safeguards]
       note: "Art. 23 is the restrictions article"
   ```
4. Re-run the command. Corrections that point at a provision that no longer exists are listed as stale.
5. If one phrase causes many wrong tags, fix the rule in `taxonomy/topics.yaml` instead of overriding
   each provision.

## Checking
`python tests/check_topics.py` verifies the gold set. Add provisions to `tests/topic_gold.yaml` as you
confirm them, so a later rule change cannot quietly break them.
