---
name: reconfirm-client-visible-repairs
description: Before a prod data repair, dry-run with a before/after diff of printed figures and re-ask if sent quotes' client-visible numbers change
metadata:
  type: feedback
---

When a prod data correction was approved on the premise "only the donut changes", the dry run showed 12 SENT quotes would also change printed bill/savings/payback. Re-asking with the concrete before/after figures was the right call; the founder then chose to correct them and asked for the list to re-send.

**Why:** online proposals re-render live, so a data fix instantly changes what clients see; the founder must know which sent quotes move.

**How to apply:** for any prod repair: dry-run inside a rolled-back transaction, diff build_quote_data before/after per quote, split drafts vs sent, re-confirm if sent client-visible figures change, then deliver the list. See [[prod-read-access]].
