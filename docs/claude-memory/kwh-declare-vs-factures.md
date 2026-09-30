---
name: kwh-declare-vs-factures
description: Founder rule 30/09/2026 — when a lead's typed monthly kWh contradicts its bills (>2× either way), BLOCK saving the quote until the lead record is corrected
metadata:
  type: project
---

Founder decision Q14 (CAD166) makes a typed monthly consumption (`conso_mensuelle_kwh`) take priority over the bills for the hourly study. On 30/09/2026 Reda ruled on the conflict case: if facture_barème(kWh déclaré) ÷ facture déclarée ∉ [0,5 ; 2], the quote screen REFUSES to save, with « kWh déclarés incohérents avec les factures — corriger la fiche du lead » under the field. Never price silently on a contradicted kWh; the options warn-only, switch-to-bills and seller-chooses were rejected.

**Why:** production quotes DEV-202609-0082/-0085 were priced on 46/32 kWh/month against bills of 90 000–180 000 MAD/year (≈×200) and printed « facture actuelle 977 MAD/an » and « rentabilisé en 25 ans ».

**How to apply:** implemented by ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES (docs/ERROR_PLAN.md). Keep the Q14 priority when the two agree. Related: [[couv-hor-donut-incident]], [[qa-coherence-auditor]].
