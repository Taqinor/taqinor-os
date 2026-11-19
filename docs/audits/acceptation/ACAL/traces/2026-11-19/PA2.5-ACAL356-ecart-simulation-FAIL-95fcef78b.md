---
sha: 95fcef78be811339bd4a89dffaa9fa6303fcc676
date: 2026-11-19
groupe: ACAL
couvre: [ACAL355, ACAL356, ACAL367, ACAL357, ACAL364, ACAL366]
couvre_avec_ecart: []
verdict: FAIL
etapes:
  - id: PA2.3-ACAL355-production-par-pan
    tache: [ACAL355]
    verdict: PASS
  - id: PA2.3-ACAL356-ACAL367-horizon
    tache: [ACAL356, ACAL367]
    verdict: PASS
  - id: PA2.3-ACAL356-matrice
    tache: [ACAL356]
    verdict: PASS
  - id: PA2.3-ACAL367-signature
    tache: [ACAL367]
    verdict: PASS
  - id: PA2.5-ACAL356-ACAL367-ecart-simulation
    tache: [ACAL356, ACAL367]
    verdict: FAIL
  - id: PA2.3-ACAL357-ombres-ajout-zone
    tache: [ACAL357]
    verdict: PASS
  - id: PA2.3-ACAL364-allee-section
    tache: [ACAL364]
    verdict: PASS
  - id: PA2.3-ACAL366-pente-section
    tache: [ACAL366]
    verdict: PASS
---

# Acceptation ACAL — 2026-11-19 (95fcef78b)

Produit par `frontend/e2e/acceptation/_enregistrement.js` (AMET90) ; le `.results.json` frère fait foi ;
relu par `python scripts/check_acceptation.py`. Oracles = qa-explorer 1-10 (`_format.md`).

| Étape | Tâches | Verdict | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Trace |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PA2.3-ACAL355-production-par-pan | ACAL355 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL355-production-par-pan.jpg |
| PA2.3-ACAL356-ACAL367-horizon | ACAL356, ACAL367 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL356-ACAL367-horizon.jpg |
| PA2.3-ACAL356-matrice | ACAL356 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL356-matrice.jpg |
| PA2.3-ACAL367-signature | ACAL367 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL367-signature.jpg |
| PA2.5-ACAL356-ACAL367-ecart-simulation | ACAL356, ACAL367 | FAIL | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.5-ACAL356-ACAL367-ecart-simulation.jpg |
| PA2.3-ACAL357-ombres-ajout-zone | ACAL357 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL357-ombres-ajout-zone.jpg |
| PA2.3-ACAL364-allee-section | ACAL364 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL364-allee-section.jpg |
| PA2.3-ACAL366-pente-section | ACAL366 | PASS | PASS | PASS | PASS | PASS | NA | NA | NA | PASS | NA | NA | docs/qa-explorer/captures/2026-11-19/ACCEPTATION-ACAL-PA2.3-ACAL366-pente-section.jpg |

- PA2.5-ACAL356-ACAL367-ecart-simulation : erreur : l’écart atelier ↔ simulation ne s’ouvre plus avec l’horizon
