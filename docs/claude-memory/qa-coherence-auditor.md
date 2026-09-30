---
name: qa-coherence-auditor
description: The 4 QA checks that find wrong-but-plausible figures (PR #743/#747) — nightly prod coherence auditor, figure parity, property/differential tests, anonymised prod data — and how to run them on real data
metadata:
  type: reference
---

Built 30/09/2026 (PR #743, tuned by #747) because 0 of 30 past wrong-figure bugs were found by CI or monitoring:
1. **Nightly coherence auditor** — `apps/ventes/coherence/` (rules in `regles_documents/etude/crm/securite.py`, tolerances in `registre.TOLERANCES`), beat task `ventes.audit_coherence_nuit` 04:15, digest to admins on NEW violations only. On-demand, read-only: `docker exec erp-agentique-django_core-1 python manage.py audit_coherence --json --no-persist` (~23 s on 310 quotes).
2. **Figure parity** — `data-figure` markers (`quote_engine/figures.py`), `test_figures_parite.py` + `frontend/e2e/figures-parite.spec.js`.
3. **Property + JS↔Python differential tests** — `test_proprietes_*.py`, `solar.properties.test.mjs`, `test_solar_differential_calculs.py` (known-divergence lists only shrink).
4. **Anonymised prod snapshot** — `qa_export_anonymise` / `qa_import_anonymise` (renamed: `core` already owns `export_anonymise`). Stream it with no file on the server: `ssh … 'docker exec erp-agentique-django_core-1 python manage.py qa_export_anonymise --company taqinor-demo --out -' > var/anon/latest.anon.json.gz`. Verified on real data 30/09: 0 of 16 658 identity values survive.

Facts learned on the first prod run (30/09): the REAL company's slug is `taqinor-demo` (legacy name — it is Taqinor's production data, not a demo). 110 violations → 100 after rule tuning (I2 rounding margin, I6 = crossing of the printed 25-year curve); real bugs filed as `ERR-QAC-*` in docs/ERROR_PLAN.md. Rendering a quote INSERTs a `ShareLink` when none is valid (`ShareLink.for_devis`) — a strictly read-only script must patch it in-process. The old prototype stays at docs/decisions/COUV-HOR/auditeur_coherence_prototype.py (its I9 is not in the nightly rules). Related: [[couv-hor-donut-incident]], [[demo-accounts-prod-incident]], [[prod-read-access]].
