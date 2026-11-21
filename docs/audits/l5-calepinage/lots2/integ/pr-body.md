## Ce que cette PR ajoute (documents seulement, rien construit)

Vague 2 du complément L5 du module calepinage (demandes de Reda des 20 et 21/11/2026) : **472 tâches v3** écrites depuis l'étude (≈ 6 100 lignes documentées, 136 constats de relecteurs sur le produit réel), réconciliées (19 doublons ou tâches devenues sans objet retirés) et routées chez le propriétaire de leurs fichiers.

**Insérées dans cette PR (41 tâches, avant `## DONE LOG`, aucun autre groupe touché)** — groupe « ACAL — complément du 2026-11-21 (vague 2) » :
- `docs/plans/PLAN_AUDIT_DEVIS.md` : 17 (porte unique de chiffrage `chiffrer_conception` + son contrat, niveau de règles 15, productible de la pose réelle au moteur horaire, dry-run `--niveau N`, activation du niveau 15 en GATED sur la lecture du dry-run par Reda, fixation des toits affleurants, marque « devis rapide », pompage interne…).
- `docs/plans/PLAN_AUDIT_MOTEUR.md` : 3 (production de la pose réelle au PDF — D-ACAL-35, économie/TRI/retour omis sans consommation — D-ACAL-39, règle de nuit production devis ↔ calepinage).
- `PLAN_AUDIT_CHANTIERS` 7, `PLAN_AUDIT_STOCK` 4, `PLAN_AUDIT_LEAD` 2, `PLAN_AUDIT_PARAMETRES` 2, `PLAN_AUDIT_DEPLOY` 2, `PLAN_AUDIT_SAV` 1, `docs/WEB_PLAN.md` 3.

**PAS inséré : le groupe principal (431 tâches) de `docs/plans/PLAN_AUDIT_CALEPINAGE.md`** — bail tenu par un autre poste (`DESKTOP-APTAHF6/dev-all-acal-m0`, qui construit le groupe du 20/11). Le bloc prêt à insérer tel quel est `docs/audits/l5-calepinage/INSERTION-PLAN_AUDIT_CALEPINAGE.md` ; une session ultérieure qui obtient le bail l'insère juste avant `## DONE LOG`.

**Décisions de Reda du 21/11/2026** ajoutées à `docs/audits/decisions.yml` (D-ACAL-35 à D-ACAL-42) et à `docs/claude-memory/calepinage-decisions-fondateur.md` (+ ligne d'index de `MEMORY.md`). D-ACAL-35 précise D-ACAL-6, QJR107 et la ligne INTERDIT « imprimer le P50 du calepinage… » de `PLAN_AUDIT_CALEPINAGE.md` (ligne laissée telle quelle).

**Dossier** `docs/audits/2026-11-21-calepinage-l5-vague2.md` : table des 472 constats (générée), comptes, réserve (55 lignes), tâches retirées, limites. **Références** recopiées depuis la branche de notes pour que les tâches les trouvent : `docs/audits/l5-calepinage/maquettes/` (13 maquettes, référence d'écran), `T1/` (rapports des relecteurs, rejeu, matrices de classes K-*), `architecture/` (décision + critique du moteur partagé).

## Gardes (lancées sur cette branche, groupe calepinage inséré en local puis retiré)
Sur cette branche (état final, sans le groupe calepinage) et, pour la forme, avec le bloc calepinage inséré en local :
- `check_taches_cablage.py` OK (31 écrans créés, 17 tâches à deux moitiés, aucun constat bloquant neuf) · `check_ancres_taches.py` 0 échec · `check_ownership.py` OK · `check_decisions.py` OK (0 signalement) · `check_plan_taches_mixtes.py` OK · `audit_registre.py --check` OK · `check_build_order.py` OK · `check_audit_dossier.py` OK · `check_stages.py` OK · `codemap_fingerprint.py --check` OK (les PLAN_AUDIT_* et WEB_PLAN sont hors empreinte).
- `python -m unittest scripts.tests.test_plan_lanes scripts.tests.test_plan_lanes_append_only scripts.tests.test_docs_calepinage_coherentes scripts.tests.test_check_decisions` : 146 tests OK (3 sautés).
- `plan_lanes.py` : REFUS = 0 pour MOTEUR, LEAD, CHANTIERS, STOCK, SAV, PARAMETRES, DEPLOY, WEB_PLAN ; DEVIS = 1, déjà présent sur `main` (ADEV116 attend ADEV46 du plan transverse), aucun refus neuf.
- **Point ouvert (non inséré ici)** : avec le bloc calepinage inséré, `plan_lanes.py docs/plans/PLAN_AUDIT_CALEPINAGE.md` passe de 23 refus (base `main`) à 216 : la porte PACT11 refuse toute tâche FRONTEND calepinage tant que 12 tâches backend qui étendent `apps/calepinage/selectors.py` (lectures croisées pour ventes et chantiers : ACAL572, 588, 595, 596, 665, 770, 883, 895, 948, 964, 997, 1008) partent dans le même run. C'est un ordre (backends d'abord), pas une erreur de texte ; à trancher par la session qui insère : accepter cet ordre en deux temps, ou déplacer ces lecteurs dans un module voisin de sélecteurs.

## Limites
- Aucun test exécuté, aucune tâche construite ; les « tests rouges d'abord » sont attendus, non mesurés.
- Lecture du code sur `207c7a70e`, ancres revérifiées sur `origin/main@919b49b7d` (l'autre poste a livré une partie du groupe du 20/11 entre-temps : trois ancres réalignées).
- Les dépendances vers un autre plan sont écrites en phrase (le planificateur ne les impose pas).
- Une critique finale doit lire cette PR avant le merge : ne pas activer l'auto-merge.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
