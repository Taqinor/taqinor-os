# PLAN_AUDIT_CHANTIERS — tâches d'audit dont J2 est propriétaire des fichiers

> **CONTRAT DE PROPRIÉTÉ (non négociable — c'est lui qui garantit zéro conflit).**
> Une session `work on the plan audit_chantiers` n'écrit QUE dans les chemins `possede` de l'unité J2 (docs/audits/unites.yml, ou docs/ownership.yml s'il existe — il prime). Tout le reste est INTERDIT en
> écriture ; lire une app étrangère = via son `selectors.py`/`services.py`/string-FK uniquement. Une
> tâche qui EXIGE d'écrire hors périmètre → `[BLOCKED: hors périmètre AUDIT_CHANTIERS]` + continuer.
> Fichiers frontend PARTAGÉS (router/nav/api/ui) : ajouts APPEND-ONLY minimaux ; conflit à
> l'update-branch = garder les DEUX ajouts. Base de test locale : `DB_NAME=erp_audit_chantiers` (jamais la
> DB partagée). La session merge sa propre branche `dev-audit_chantiers` vers main (update-branch → CI →
> auto-merge) ; conflit sur `docs/CODEMAP.md` (fingerprint structure) = prendre l'arbre mergé et relancer
> `python scripts/codemap_fingerprint.py --write`. Ce fichier n'est PAS dans la surface du
> plan-fingerprint : tick + DONE LOG ici, jamais CODEMAP §10. Les 7 leçons de
> docs/claude-memory/lecons-construction-qjr5.md sont des critères d'acceptation de chaque tâche, et la
> tâche d'acceptation live de chaque groupe est jouée par l'orchestrateur AVANT le merge.
> Ne pas lancer en même temps que : PLAN_AUDIT_TRANSVERSE.md.

## Groupe ACAL — audit calepinage du 2026-10-04 (dossier docs/audits/2026-10-04-calepinage.md)

**Provenance, décisions gravées (D-ACAL-1..28 + défauts), séquencement, NE PAS FAIRE et non couvert :**
dans l'en-tête du groupe de `docs/plans/PLAN_AUDIT_CALEPINAGE.md` — ils valent ICI à l'identique (même
groupe ACAL, METHODE §D.3 règle 6 : les tâches gardent le préfixe de l'unité auditée quel que soit le
fichier du propriétaire). **351 tâches ACAL** au total : `docs/plans/PLAN_AUDIT_CALEPINAGE.md` 271 · `docs/plans/PLAN_AUDIT_TRANSVERSE.md` 44 · `docs/plans/PLAN_AUDIT_DEPLOY.md` 14 · `docs/plans/PLAN_AUDIT_DEVIS.md` 12 · `docs/plans/PLAN_AUDIT_ANALYSE.md` 4 · `docs/plans/PLAN_AUDIT_MOTEUR.md` 2 · `docs/plans/PLAN_AUDIT_LEAD.md` 1 · `docs/plans/PLAN_AUDIT_CHANTIERS.md` 1 · `docs/plans/PLAN_AUDIT_SECURITE.md` 1 · `docs/WEB_PLAN.md` 1. Ce fichier : 1 tâches
(M2 1). Un `@after` vers une tâche d'un AUTRE fichier PLAN_AUDIT_* est un prérequis à vérifier sur
`origin/main` avant de démarrer (plan_lanes ne voit que son lot).

### ACAL — M2

- [ ] ACAL274 — **Le bloc « calepinage » du chantier affiche le kWc et les modules VENDUS (lignes du devis) et l'écart au dessin comme tel** : **P1.** Constat : C-ACAL-118 (C3, S2). Given DEV-202610-0010 (12 × 550 W = 6,6 kWc) dont le dessin dit 8,52 kWc / 12 modules ; When calepinage_retenu_du_chantier (installations/selectors.py:25-60) → CalepinageRetenuCard.jsx ; Then kwc = 6,6 et modules = 12 lus via apps.ventes.selectors (puissance_kwc_du_devis / lignes) ; le dessin (mesures_du_document sur Calepinage.roof_layout, D-ACAL-2) est affiché « dessin : 8,52 kWc » avec l'écart ; la branche `pose = resultat.get('pose')` de calepinage.selectors.calepinage_retenu_pour_devis (:327-345, hors Files PACT11) ne fournit plus les chiffres. Persistance : n/a — lecture. Client : n/a — chantier interne. Test rouge d'abord : backend/django_core/apps/installations/tests/test_acal_chantier_kwc_vendu.py::test_bloc_chantier_kwc_vendu — aujourd'hui 8,52 (sonde exécutée sur DEV-202610-0010) ; frontend/src/features/installations/CalepinageRetenuCard.test.jsx (réécrit : vendu + dessin). Test-du-test : Réversion : relire roof_layout.result.kwc ⇒ échec. Source réelle : scenario.puissance_kwc_du_devis ; mesures_du_document (D08-T19). Appelants : installations/selectors.py:25-60 ← installations/serializers.py:579, installations/services.py:555-560 ; CalepinageRetenuCard.jsx. Jumeaux : Supprimée : lecture kwc/panels du layout pour le chantier (calepinage/selectors.py:327-345). Survivant : puissance_kwc_du_devis pour le vendu, mesures_du_document pour le dessin. Listes figées : n/a. Contrat partagé : n/a — clé `dessin_kwc` additive. Déployable : Back + écran ; check_dockerfile_context.mjs vert. Preuve en direct : P9.1 — S-H : chantier de DEV-202610-0010 : « 6,6 kWc vendus — dessin 8,52 kWc ». Hors périmètre : Bascule de la source vers Calepinage.roof_layout (D-ACAL-2, C-ACAL-087). Files: `backend/django_core/apps/installations/selectors.py`, `frontend/src/features/installations/CalepinageRetenuCard.jsx`, `backend/django_core/apps/installations/tests/test_acal_chantier_kwc_vendu.py`, `frontend/src/features/installations/CalepinageRetenuCard.test.jsx` (ROUTINE) (@after: ACAL107, ACAL108, ACAL273) (@lane: calepinage/cycle) (@model: sonnet)

## DONE LOG
