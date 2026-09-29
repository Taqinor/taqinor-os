---
name: qa-coherence-auditor
description: QA gap audit 30/09/2026 — why wrong-but-plausible figures escape all QA, and the read-only prod document-consistency auditor prototype
metadata:
  type: reference
---

Prototype: docs/decisions/COUV-HOR/auditeur_coherence_prototype.py (run with manage.py shell on prod, read-only, rolled back; 310 quotes in ~15 s). Report: docs/decisions/COUV-HOR/README.md §6.

Key facts: of 30 past bugs in this family, 0 were found by CI and 0 by prod monitoring; independent rules worth alerting on are I4 (conso = bills÷1.20), I2 (donut vs −N % in top tranche), I5 (printed current bill vs real bills), I7 (hourly block kWc ≠ quote kWc), I10 (monthly chart vs option card). I1/I3/I11 are regression-only or noisy. Top recommendation not yet built: nightly read-only auditor alerting on NEW violations (apps/ventes/coherence + beat task). Related: [[couv-hor-donut-incident]].
