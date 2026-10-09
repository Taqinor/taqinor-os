---
name: apar-decisions-fondateur
description: 09/10/2026 — D-APAR-1 : le profil tva_standard est l'unique source du taux de TVA par défaut ; bouton « Par défaut » du référentiel retiré
metadata:
  type: project
---

Audit paramètres (groupe APAR, `docs/plans/PLAN_AUDIT_PARAMETRES.md`). Option (a) recommandée retenue, choisi par Reda via la question interactive du 09/10/2026 (ne jamais re-demander) :

- **D-APAR-1 = (a)** (APAR1) : le profil `tva_standard` (Paramètres › Société) reste l'unique source du taux de TVA par défaut d'une société ; le bouton « Par défaut » du référentiel Taux de TVA est retiré (le référentiel garde la liste des taux applicables).

**Why:** `set_defaut` du référentiel n'était lu par aucun devis (sonde : référentiel 14 %, profil 20 %).
**How to apply:** APAR44 applique D-APAR-1 (reste gatée par D-APAR-2, APAR2).
