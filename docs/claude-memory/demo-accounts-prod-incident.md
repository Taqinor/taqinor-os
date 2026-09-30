---
name: demo-accounts-prod-incident
description: CLOSED 30/09/2026 — seeded demo accounts (published password) were active on production; deactivated; demo documents neutralised
metadata:
  type: project
---

Found 30/09/2026 by the first production run of `audit_coherence` (PR #743): production has ONE company, slug `taqinor-demo` (the real business — legacy name), and `seed_demo` data had been loaded into it on 10/06 — users `demo_admin` (administrator role) and `demo_resp`, whose password is written in the PUBLIC repo (`seed_demo.py`, `frontend/e2e/helpers.js`).

Resolution (all 30/09, each with Reda's explicit OK):
- Both accounts DEACTIVATED (`is_active=False`, reversible); `authentication/cookie_auth.py:78` rejects inactive users on every request. The last login (16/07, « appareil inconnu ») was confirmed by Reda as his team — incident CLOSED.
- The 9 DEMO documents neutralised by status (no archive exists for devis/BC/factures and the trash app does not cover them): DEV-DEMO-0001 brouillon→refuse, DEV-DEMO-0003 accepte→refuse, BC-DEMO-0001 livre→annule, BC-DEMO-0002 en_attente→annule, FAC-DEMO-0002 payee→annulee (others were already expired/refused/cancelled). Previous statuses listed here to reverse if ever needed.
- The seed's products, clients and leads STAY: real business uses them (e.g. INST-STD in 281 real quotes, ACC-KIT 258, SOC-STD 260; clients Tazi/Berrada and the 3 seed leads carry real documents).
- Guard: nightly rule `SEC_COMPTE_DEMO_ACTIF` (apps/ventes/coherence/regles_securite.py) alerts if a seeded account is active again in production.

**Why:** a published admin password on the real company is a critical exposure; the repo is public.

**How to apply:** never run a seed command against production; never reactivate these accounts; treat any SEC_COMPTE_DEMO_ACTIF alert as urgent; never delete the seed's catalogue items. Related: [[prod-read-access]], [[qa-coherence-auditor]].
