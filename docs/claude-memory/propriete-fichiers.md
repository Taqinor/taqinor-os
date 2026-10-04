---
name: propriete-fichiers
description: Règle fondateur 02/10/2026 — une tâche va dans le plan du propriétaire de ses fichiers ; multi-propriétaires → plan transverse ; registre docs/ownership.yml gardé par scripts/check_ownership.py
metadata:
  type: feedback
---

**Une tâche va dans le plan du propriétaire de ses fichiers ; multi-propriétaires → plan transverse.**

Chaque fichier sous `backend/django_core/apps`, `backend/django_core/core`, `frontend/src`, `apps/web` a
UN propriétaire, déclaré dans `docs/ownership.yml` (globs `paths` précis, puis `fallback` par sous-arbre).
Propriétaires = les unités d'audit de [[audits-modules]] (leads, fiche, cadence, clients, visites,
calepinage, devis, facturation, stock, chantiers, sav, ged, portail, parametres) + publicite, analyse,
web, platform, parked, et `transverse` qui ne possède AUCUN fichier. Chaque propriétaire a son plan
`docs/plans/PLAN_<PROPRIÉTAIRE>.md` (lancé par « work on the plan <propriétaire> », créé par le premier
audit qui y route une tâche) ; `transverse` = `docs/plans/PLAN_TRANSVERSE.md`.

- Rédiger une tâche (audit, add to plan, ERR…) : lister ses `Files:`, demander leur propriétaire
  (`python scripts/check_ownership.py --owner-of <chemins>`) ; un seul → son plan ; plusieurs → plan
  transverse. Un fichier neuf doit être revendiqué au registre dans le même commit.
- Surfaces `append_only` du registre (routes, barrels, index.css, échantillons de contrat, `migrations/`…) :
  tout propriétaire y AJOUTE selon la règle écrite à côté, sans réordonner ni réécrire. Migrations :
  si deux sessions créent la même tête, celle qui fusionne en second régénère SA migration au-dessus
  (jamais de migration de fusion).
- Le plan transverse et les files historiques multi-propriétaires (PLAN.md, PLAN2.md, new_tasks_plan.md,
  ERROR_PLAN.md, FRONTEND_GAP_PLAN.md) ne tournent JAMAIS en parallèle d'un plan dont ils touchent un
  propriétaire.
- Un fichier-dieu garde un propriétaire intérimaire ; une tâche d'un autre propriétaire qui le touche
  est transverse jusqu'à sa découpe (tâches SPL, docs/plans/PLAN_TRANSVERSE.md).

**Why:** Reda, 02/10/2026 — les sessions parallèles ne marchent que si la propriété est réelle et
disjointe ; la construction QJR5 a dû faire passer 155 de ses 159 tâches dans une seule lane série
parce que DevisGenerator.jsx, views/devis.py, solar.js, builder.py, crm/services.py… étaient partagés.
Cette règle remplace, pour le routage, la sortie « ONE new group in docs/PLAN2.md » du bloc commun
d'[[audits-modules]].

**How to apply:** la garde `scripts/check_ownership.py` (job `stage-names`) refuse un fichier sans
propriétaire ou à deux propriétaires, une tâche d'un plan de propriétaire qui déclare un fichier d'un
autre, et un fichier neuf non déclaré ; `scripts/plan_lanes.py` affiche les propriétaires de chaque
lane et liste les tâches multi-propriétaires. Voir [[lecons-construction-qjr5]] pour les critères
d'acceptation des tâches de découpe.
