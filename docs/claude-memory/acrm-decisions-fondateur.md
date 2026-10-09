---
name: acrm-decisions-fondateur
description: 09/10/2026 — D-ACRM-5 (portée de l'opposition « ne plus contacter ») et D-ACRM-6 (routes CRM sans écran : retirer i/iv, parquer ii/iii)
metadata:
  type: project
---

Audit crm (groupe ACRM ; `docs/plans/PLAN_AUDIT_TRANSVERSE.md`, en-tête dans `docs/plans/PLAN_AUDIT_CRM.md`). Réponses de Reda via la question interactive du 09/10/2026 (ne jamais re-demander) :

- **D-ACRM-5 (ACRM1) — opposition « ne plus contacter » (loi 09-08 art. 9)** :
  - (1) = (a) : un lead opposé est exclu de TOUT export d'audience publicitaire (audiences Meta, graine lookalike, segments marketing) → ACRM56 dé-GATED.
  - (2) = (a) : après un effacement (DSR ou rétention 3 ans), on garde UNIQUEMENT une empreinte hachée de l'e-mail/téléphone, liste d'opposition qui refuse toute nouvelle prospection automatique → ACRM62.
  - (3) = (a) : si la personne opposée demande elle-même un rappel depuis sa proposition, on pose la touche et on lève le drapeau avec une note datée « opposition levée à la demande du client » → ACRM63.
- **D-ACRM-6 (ACRM2) — routes CRM servies sans écran** :
  - (i) `relance-etapes/kpi-adherence/` + `mes-stats/` = (a) retirer la route et son calcul → ACRM64.
  - (ii) salles de vente = (b) parquer derrière un réglage société éteint par défaut, sans calcul en arrière-plan → ACRM65.
  - (iii) apporteurs + deals enregistrés + `deals-enregistres/a-payer/` = (b) parquer derrière un réglage société éteint par défaut, aucune commission calculée tant qu'il est éteint → ACRM66.
  - (iv) `defis/<id>/export-xlsx/`, `points-contact/attribution/`, `clients/segments/` = (a) retirer la route et son calcul → ACRM67 (ACRM44 cochée sans objet).
  - Liste blanche de `check_routes_appelees.py` (ACRM49) = exactement les routes parquées (ii)/(iii) sans appelant front → ACRM68 (PLAN_AUDIT_DEPLOY).

**Why:** parquer ≠ retirer : les routes (ii)/(iii) restent (éteintes), donc (iii) est « gardée » au sens d'ACRM2 — ACRM57 (table de transitions des deals, pas un écran) est dé-GATED pour durcir des routes qui restent activables. Aucun écran apporteurs ni salles n'est commandé.
**How to apply:** ne jamais reconstruire les routes (i)/(iv) ; tout nouveau code apporteurs/salles lit le réglage société et ne calcule rien quand il est éteint.
