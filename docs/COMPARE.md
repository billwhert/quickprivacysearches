# Compare view

A comparison set puts the same question side by side across laws. Sets are written by hand in
`compare/*.yaml`; nothing is generated. Exact text is pulled from the stored provisions.

```yaml
id: breach-notification
title: Breach notification
question: Who must be told about a data breach, and by when?
columns:
  - doc: gdpr                      # the law this column is about (also the show/hide toggle)
    heading: "GDPR: notifying the authority and individuals"
    chunk_ids: ["gdpr:art:33:1", "gdpr:art:34:1"]
  - doc: ccpa
    docs: [ccpa, ccpa_regs]        # optional: a column may draw on more than one document
    heading: "CCPA: civil actions after certain breaches"
    note: Optional short note shown above the provisions (use it when a law has no equivalent).
    chunk_ids: ["ccpa:sec:1798.150:a"]
```

- At least two columns, one per law. The build stops if a provision id does not exist or belongs to a
  document the column does not list.
- Headings describe what the provisions say. The page footer states that placing provisions side by side
  is an editorial selection, not a statement that they are equivalent.
- To add a comparison, add a YAML file and rebuild. It appears on `/compare/` and in the nav automatically.
