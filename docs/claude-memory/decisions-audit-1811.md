---
name: decisions-audit-1811
description: 18/11/2026 — D-ADRG-15 : le rapport figé « stock » exige le droit d'export du stock (`stock_export`) en plus de celui des rapports, sur toutes ses sorties ; tâche ADRG158
metadata:
  type: project
---

Reda a répondu le 18/11/2026 (question interactive, session `loop audit`) à la question relevée trois fois par les
contre-visites ADRG (14, 17 et 18/11, §5 « non déposés ») : « Le rapport figé "stock" doit-il exiger le droit d'export
du stock ? » Réponse : **exiger** (D-ADRG-15 dans `docs/audits/decisions.yml`). Rien n'est construit par la réponse :
elle ouvre la tâche ADRG158 (`docs/plans/PLAN_AUDIT_TRANSVERSE.md`, propriétaires analyse et securite : le test de la
grille `apps/roles/tests.py` est réaligné dans le même commit).

**Why:** le rapport figé sort le nom, la référence et la quantité de chaque produit, le même contenu que l'export du
stock et que la requête `stock_produits`, déjà gardés par `stock_export` (ADRG123, ADRG146). D-ASEC-VER4-1 a retiré ce
droit au Commercial responsable et au Responsable : sans la règle, ils exportaient quand même le stock par le genre figé.

**How to apply:**
- Toutes les sorties du genre `stock` : créer et modifier un envoi programmé (PATCH compris), l'envoi par la tâche
  planifiée (droit du propriétaire relu à chaque envoi), le lien public, WhatsApp, et l'export xlsx/pdf de la carte
  Stock de `/rapports` (`reports/stock/?export=`). La lecture à l'écran (JSON) ne change pas.
- Une seule règle : la garde par jeu existante (`exiger_export_dataset` sur `stock_produits`), et `DroitDeLaGrille`
  sur la route d'export ; jamais un second mécanisme.
- Un envoi `stock` existant dont le propriétaire n'a pas le droit n'est jamais supprimé : il ne part plus et
  l'historique dit pourquoi (ligne « échec » au motif lisible).
- À l'écran : le bouton d'export de la carte Stock est masqué et le genre Stock grisé avec son motif, jamais un 403 nu.
- Hors décision : les genres figés `sales` et `service` (comptes agrégés, sans nom ni prix).
