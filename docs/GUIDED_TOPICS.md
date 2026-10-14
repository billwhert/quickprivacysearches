# Guided topics

A guided topic is a hand-built research path for a common question. It gathers the provisions that
bear on the question, in order, with the exact text, citation, version and retrieval date of each.
It describes what the law says. It never says what an organization must do, and it drafts nothing.

## Files
| File | Purpose |
|---|---|
| `topics/<id>.yaml` | One topic: title, scope, trigger words, applicability questions, ordered items, related links |
| `data/reports/guided_topics_review.md` | Generated review sheet: every cited provision with its full text and a checkbox |
| `build/guided.py` | Loading, validation, review status and the `approve` command |

## The shape of a topic file
```yaml
id: ca-cookies-tracking
title: Cookies and tracking (California)
scope: One sentence on what it covers.
status: draft            # draft | published
triggers: [cookies, "do not sell", website]   # one word scores 1, a phrase 2; shown at 2 or more
docs: [ccpa, ccpa_regs, gdpr]         # laws it draws on (keeps it away from other-law questions)
applicability:           # "does the law apply at all?"
  - question: Is the organization a "business" under the CCPA?
    note: Optional short summary, shown labelled as a summary.
    chunk_ids: ["ccpa:sec:1798.140:d"]
items:                   # the ordered list of what the provisions say
  - label: What the CCPA says about the right to opt out of sale or sharing
    chunk_ids: ["ccpa:sec:1798.120:a", "ccpa:sec:1798.120:b"]
related:
  - label: California business privacy notice
    topic: ca-business-privacy-notice
```
Provision ids look like `ccpa:sec:1798.120:a` (document, section, subdivision). The review sheet lists
the id next to every provision, and they are all in `data/processed/<doc>/chunks.json`. The text is
pulled from there; it is never retyped.

## Reviewing and publishing
1. Read `data/reports/guided_topics_review.md`. For each provision: is it the right one, is anything
   missing, and does the heading describe what the law says?
2. Edit the YAML to add or remove provisions. Run `python build/guided.py review` to regenerate the sheet.
3. Publish: `python build/guided.py approve ca-cookies-tracking --by "Your name"`. This sets
   `status: published`, records the review date, and stores a fingerprint of every cited provision.
4. Commit and push.

## What happens after publishing
- If a rebuild changes the text of any cited provision (for example, a new law version), the topic is
  flagged **Needs review** on the site and in the build output until you approve it again.
- Drafts are left out of the production site. To preview drafts locally: set `INCLUDE_DRAFT_TOPICS=1`
  when running `python build/build.py`.
- `python build/guided.py status` prints one line per topic.
