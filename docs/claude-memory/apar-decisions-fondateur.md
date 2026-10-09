---
name: apar-decisions-fondateur
description: 09/10/2026 — D-APAR-1 : le profil tva_standard est l'unique source du taux de TVA par défaut ; D-APAR-2 : écran Approbations retiré, discount_approval_threshold seul réglage
metadata:
  type: project
---

Audit paramètres (groupe APAR, `docs/plans/PLAN_AUDIT_PARAMETRES.md`). Option (a) recommandée retenue, choisi par Reda via la question interactive du 09/10/2026 (ne jamais re-demander) :

- **D-APAR-1 = (a)** (APAR1) : le profil `tva_standard` (Paramètres › Société) reste l'unique source du taux de TVA par défaut d'une société ; le bouton « Par défaut » du référentiel Taux de TVA est retiré (le référentiel garde la liste des taux applicables).
- **D-APAR-2 = (a)** (APAR2) : l'écran Paramètres › Approbations est retiré et ses routes d'écriture masquées ; `CompanyProfile.discount_approval_threshold` reste l'unique réglage du seuil de remise.

**Why:** `set_defaut` du référentiel n'était lu par aucun devis (sonde : référentiel 14 %, profil 20 %).
D-APAR-2 : `ApprovalPolicy.requires_approval` n'avait aucun appelant de production (grep VB : 0) ; le seuil réellement appliqué est celui du profil.
**How to apply:** APAR44 applique D-APAR-1 et D-APAR-2 (option (a) des deux).
