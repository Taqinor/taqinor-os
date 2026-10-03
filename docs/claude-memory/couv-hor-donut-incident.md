---
name: couv-hor-donut-incident
description: Coverage-donut / bills÷1.20 incident on taqinor-os quotes (29–30/09/2026) — what shipped, prod repairs, what is still open
metadata:
  type: project
---

Quote DEV-202609-0113 (Khalid) printed "28 % couverture" next to "−37 %"; real 37 %. The donut recomputed prod×taux÷etude_params.conso_annuelle, and conso_annuelle had been stored as bills ÷ 1.20 MAD/kWh (lead without distributor → frontend flat fallback). 134 residential quotes affected since ~20/08.

State as of 2026-09-30:
- Fix merged: PR Taqinor/taqinor-os#738 (merge 62542682) — donut reads the hourly engine; DevisGenerator no longer re-saves a bills-derived conso; CAD167 mirror (named distributor → national grid) in solar.js + pricing._table_tarifaire; builder applies company grid to any distributor.
- Prod data repaired: DEV-202609-0113 (165000→123024, PDF regenerated) and 128 quotes (84 drafts, 35 sent, 9 expired) via domain.etude_schema.ecrire; rescan = 0 left with the ÷1.20 signature.
- Full handoff (incl. the 12 sent quotes to re-send, QA audit, prototype auditor): docs/decisions/COUV-HOR/README.md (PR #739).

**Why:** founder wants to track this from other machines/accounts; the repo doc is the source of truth, this memory is the pointer.

**How to apply:** open items — re-send the 12 sent quotes (founder); bug in apps/ventes/domain/etudes.py rafraichir_etude_horaire_devis summing both variantes' panels (60 stale hourly blocks, fixed in a separate session started 30/09 — check its PR); C&I 60 %/80 % autoconso model question — FERMÉE le 03/10/2026 par D-CIQ-1 (horaire sur profil déclaré, [[ci-decisions-fondateur]]). See [[ci-autoquote-conso-only]], [[qa-coherence-auditor]], [[prod-read-access]].
