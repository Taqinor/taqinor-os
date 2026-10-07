---
name: propriete-fichiers
description: Règle fondateur 02/10/2026 — une tâche va dans le plan du propriétaire de ses fichiers ; multi-propriétaires → plan transverse ; registre docs/ownership.yml gardé par scripts/check_ownership.py
metadata:
  type: feedback
---

**Une tâche va dans le plan du propriétaire de ses fichiers ; multi-propriétaires → plan transverse.**

Chaque fichier du code et de l'outillage (`backend/`, `frontend/`, `apps/web`, `scripts/`, `.github/`,
`services/`… — pas docs/ ni CLAUDE.md) a UN propriétaire, déclaré dans `docs/ownership.yml`. Propriétaires = les unités de
`docs/audits/unites.yml` qui possèdent des fichiers (acquisition J0, lead J1a, crm D1, devis J1b,
facturation J5, moteur D2, generateur D4, calepinage D3, chantiers J2, stock J3, documents J6, sav J4,
parametres X3, securite X1, deploy X5, analyse X7) + `web` (docs/WEB_PLAN.md) + `parked` + `platform`
(files historiques PLAN/PLAN2/new_tasks/ERROR_PLAN/FRONTEND_GAP, aucun fichier) + `transverse` (aucun
fichier). Plan d'un propriétaire : `docs/plans/PLAN_AUDIT_<MOT>.md` (« work on the plan audit_<mot> ») ;
transverse : `docs/plans/PLAN_AUDIT_TRANSVERSE.md`. Le registre PRIME sur le champ `possede` de unites.yml.

- Rédiger une tâche (audit, add to plan, ERR…) : lister ses `Files:`, puis
  `python scripts/check_ownership.py --owner-of <chemins>` ; un seul propriétaire → son plan ; plusieurs →
  plan transverse. Un fichier NEUF doit être revendiqué dans `docs/ownership.yml` dans le même commit.
- Un test suit son sujet (DevisGenerator* = generateur, tests du moteur = moteur…).
- `apps/web` reste au propriétaire `web` (session WEB_PLAN, déploiement Cloudflare) sauf le studio toiture
  (calepinage) : mesuré le 04/10, ses pages proposition/questionnaire et `lib/lead.ts` sont éditées par la
  session web ; une tâche qui change à la fois une page apps/web et le backend ERP est transverse.
- Un `@after` vers une tâche d'un AUTRE plan est attendu : `plan_lanes.py` refuse la tâche tant que sa
  dépendance n'est pas cochée (lancer d'abord l'autre plan ; `--force-wave` = fondateur seulement).
- Mesurer : `python scripts/check_ownership.py --conflits 40` (fichiers partagés classés par coût).
- Surfaces `append_only` du registre (migrations/, urls.py, apps.py, façade ventes/services.py,
  core/events.py, roles/permissions_registre.py (+ notifications/types_evenements.py, audit/modeles_suivis.py, publicapi/portees.py), index.css, router, module.config.jsx…) : tout propriétaire y AJOUTE
  selon la règle écrite à côté, sans réordonner ni réécrire. Migrations : si deux sessions créent la même
  tête, celle qui fusionne en second régénère SA migration au-dessus (jamais de migration de fusion).
- Le plan transverse, PLAN_CRM_VENTES.md et les files historiques ne tournent JAMAIS en parallèle d'un
  plan dont ils touchent un propriétaire.
- Un fichier-dieu garde un propriétaire intérimaire ; une tâche d'un autre propriétaire qui le touche est
  transverse jusqu'à sa découpe (groupe SPL : déplacements purs, golden capturé avant, ancien code
  supprimé dans le même commit).

**Why:** Reda, 02→04/10/2026 — les sessions parallèles ne marchent que si la propriété est réelle et
disjointe ; la construction QJR5 a dû faire passer 155 de ses 159 tâches dans une seule lane série parce
que DevisGenerator.jsx, views/devis.py, solar.js, builder.py, crm/services.py… étaient partagés (mesure du
04/10 : 967 fichiers sur 14 277 touchés par au moins deux propriétaires).

**How to apply:** la garde `scripts/check_ownership.py` (job `stage-names`) refuse un fichier sans
propriétaire ou à deux propriétaires, une tâche ouverte d'un plan de propriétaire qui déclare le fichier
d'un autre, un plan non lié au registre et un fichier neuf non déclaré ; `scripts/plan_lanes.py` affiche
les propriétaires de chaque lane et liste les tâches multi-propriétaires. Critères d'acceptation des tâches
de découpe : [[lecons-construction-qjr5]]. Routage côté audit : skill `audit`, docs/audits/METHODE.md §D.3.
