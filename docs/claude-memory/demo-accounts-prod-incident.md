---
name: demo-accounts-prod-incident
description: Seeded demo accounts (published password) were active on production — deactivated 30/09/2026; demo documents still in the real company
metadata:
  type: project
---

Found 30/09/2026 by the first production run of `audit_coherence` (PR #743): production has ONE company, slug `taqinor-demo` (the real business, 310 real quotes), and `seed_demo` data had been loaded into it on 10/06 — users `demo_admin` (administrator role) and `demo_resp`, whose password is written in the PUBLIC repo (`seed_demo.py`, `frontend/e2e/helpers.js`).

State:
- Both accounts DEACTIVATED on 30/09 with Reda's explicit OK (`is_active=False`, reversible). `authentication/cookie_auth.py:78` rejects inactive users on every request, so open sessions/tokens died too.
- Audit log: `demo_admin` was used as a working account 18/06–16/07 (26 logins, 81 updates, 12 creates, WhatsApp, PDFs); 0 failed logins; last login 16/07 17:40 raised "Nouvelle connexion depuis un appareil inconnu" (Windows 10 / Chrome) — OPEN: Reda to confirm it was him (reads are not audited).
- OPEN (founder decision): demo documents still in the real company — DEV-DEMO-0001..0005 (one `accepte`, 110 464,80), 2 BC, FAC-DEMO-0001 (annulée) and FAC-DEMO-0002 (`payee`) — they skew sales/revenue figures. Never delete without Reda's go.
- Guard: nightly rule `SEC_COMPTE_DEMO_ACTIF` (apps/ventes/coherence/regles_securite.py) alerts if any seeded account is active again in production.

**Why:** a published admin password on the real company is a critical exposure; the repo is public.

**How to apply:** never run a seed command against production; never reactivate these accounts; treat any new SEC_COMPTE_DEMO_ACTIF alert as urgent. Related: [[prod-read-access]], [[qa-coherence-auditor]].
