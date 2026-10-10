# Vérifie AACQ — contre-visite de clôture du groupe acquisition (J0), 10/10/2026

Commande « vérifie AACQ » (METHODE §C.4.2, skill audit §5). Le groupe compte **65 tâches cochées sur 66**, soit 98 % : la
contre-visite de **clôture** (≥ 95 %) est due. Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou
les commits et le test nommé, en appliquant les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. L'écart S2 est
prouvé par une sonde exécutée en transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du
propriétaire de leurs fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `5ea32b58b` (PR #934). Branche de claim : `verifie-aacq`.
- **Registre.** J0 `acquisition`, statut `audité`, groupe AACQ, dossier `docs/audits/2026-10-08-acquisition.md` (PR #865).
  Tâches AACQ par plan : ACQUISITION 57, WEB_PLAN 5, TRANSVERSE 2, CHANTIERS 1, DEPLOY 1.
- **Inventaire (déterministe).** 66 tâches AACQ, dont 65 `[x]`. La seule restante est AACQ89, l'acceptation live du
  groupe, ouverte. Les trois décisions fondateur (AACQ90, AACQ95, AACQ96) sont tranchées. `audit_registre.py --du` :
  « AACQ (J0 acquisition) : 98 % cochées (65/66) — vérifie dû, clôture ».
- **Échantillon (graine = SHA `5ea32b58b`).** Aucune tâche P0 ou S1 cochée. 25 % du reste : **16 tâches** sur 65 —
  AACQ8, AACQ10, AACQ15, AACQ18, AACQ20, AACQ26, AACQ35, AACQ37, AACQ38, AACQ60, AACQ61, AACQ62, AACQ66, AACQ68, AACQ90,
  AACQ97.
- **Pile locale.** Le partage de disque de Docker Desktop était cassé : le conteneur Django partagé ne lisait plus le code.
  Un conteneur jetable `sonde-verifie` a été créé depuis l'image `erp-agentique-django_core`, avec le code de `main` copié
  dedans, sur la base de démo `erp_db`. Aucune migration n'était en attente. La base partagée n'a pas été touchée.

## 1. Vérificateurs (3 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel | autre |
|---|---|---|---|---|
| 1 | AACQ8, AACQ10, AACQ15, AACQ18, AACQ20, AACQ26 | 4 | AACQ10, AACQ26 | — |
| 2 | AACQ35, AACQ37, AACQ38, AACQ60, AACQ61 | 4 | AACQ60 (S4) | AACQ37 : texte vieilli |
| 3 | AACQ62, AACQ66, AACQ68, AACQ90, AACQ97 | 3 | AACQ68, AACQ90 | — |
| **Total** | **16** | **11** | **5** | — |

Commits lus : AACQ8 `90b3bc5`, AACQ10 `6046023`, AACQ15 `f0a11b5`, AACQ18 `de9f77c`, AACQ20 `150c6a6`, AACQ26 `3cb2829`,
AACQ35 `67eea08d1`, AACQ37 `9cfba59b3`, AACQ38 `142ae837c`, AACQ60 `26c18b1ec`, AACQ61 `a06b9ac32`, AACQ62 `47db6ea7b`,
AACQ66 `5c942551f`, AACQ68 `63a2c2d93`, AACQ90 `8fd989d61` (avec AACQ3 `48e50f227`), AACQ97 `d4325c592`.

Les points saillants :

- **AACQ90 est la décision du fondateur sur la devise** (D-AACQ-1 = a : seuils et plafonds saisis et affichés dans la
  devise du compte, sans taux). AACQ3 l'a appliquée côté serveur. La contre-visite trouve deux trous : la devise est posée
  même quand aucun montant n'est saisi, et aucun écran ne l'affiche (§3, §4).
- **AACQ26 a posé la fonction unique `metrics.cout_par_lead`**, mais le coût par lead Odoo de `odoo_leads.py` est encore
  calculé à la main, et la garde AST ne lit que 4 fichiers. La source nommée par le serveur n'est affichée par aucun écran.
- **AACQ10 et AACQ68 ont un code juste**, mais leurs tests ne tuent pas le mutant décrit (leçon 5).
- **AACQ60 est juste sur le fond.** Le contrat a été livré dans la même PR #899 que ses consommateurs, au lieu d'être seul
  sur `main` d'abord (séquencement PACT10). Il n'y a rien à corriger : S4, sans tâche.
- **AACQ37 a un écart de texte, sans écart de code** : la ligne citée a bougé (237 → 244). Aucune tâche.

## 2. Tests nommés

- **Aucun test Django ni vitest n'a été rejoué par les vérificateurs.** Ils ont lu les commits et les tests nommés.
- **Exécuté.** La garde AST d'AACQ26 (`test_aacq_parite_cpl.py::divisions_hors_fonction`) a été appliquée à tous les
  fichiers d'`apps/adsengine` par le vérificateur du lot 1 : elle trouve `odoo_leads.py [281]`. Rejouée à la rédaction :
  même résultat. Un balayage des divisions affectées à un nom `cpl` (rédaction) trouve en plus `odoo_leads.py` l. 246 et
  287, et `views.py` l. 2829 et 4285 ; `views.py` l. 4301 (`cpl_norm`) divise un seuil par un CPL et n'est pas visé.
- **CI de `main` à `5ea32b58b`.** Les runs « CI » (push et merge_group) sont en succès (`gh run list`). Le run planifié
  « Release verify (full suite) » du même commit est en échec ; il n'a pas été examiné ici (§5).

## 3. Sondes (orchestrateur, conteneur jetable `sonde-verifie`, transaction annulée)

La sonde suit le format du lanceur `scripts/sonde.py` (`SONDE`, `sonde(ctx)`) : `python scripts/sonde.py AACQ/C-AACQ-VER-001`.

| Sonde | Tâche | Verdict | Sortie |
|---|---|---|---|
| `docs/audits/sondes/AACQ/C-AACQ-VER-001.py` | AACQ90 (AACQ3) | **REPRO** | « règle 201 devise='USD' seuil_par_défaut=250 applicable=True ; garde-fou PATCH 200 devise_base='USD' devise_exposée_GET=False » |

Lecture de la sortie :

- Sur un compte Meta en USD, armer la règle `stop_loss_cpl` SANS saisir de seuil (le corps exact du bouton « Armer » de
  l'écran Règles) pose la devise USD. Le seuil par défaut, 250, calibré en MAD, devient 250 USD et la règle est déclarée
  applicable. C'est l'inverse de D-AACQ-1 : aucun montant n'a été saisi dans la devise du compte.
- Le PATCH des garde-fous pose bien `ceiling_currency` = USD, mais le GET de `/guardrail/` ne la sert pas. L'écran
  Connexion affiche toujours « (MAD) » à côté des plafonds.

## 4. Écarts retenus

Constats : C-AACQ-VER-001 (AACQ90), C-AACQ-VER-002 (AACQ26), C-AACQ-VER-003 (AACQ68), C-AACQ-VER-004 (AACQ10). Fichier du
propriétaire, vérifié par `check_ownership.py --owner-of` pour chaque fichier : `acquisition` pour AACQ98-AACQ105,
`lead` pour AACQ106.

| Tâche | Écart de | Gravité | Cause | Preuve |
|---|---|---|---|---|
| AACQ98 | AACQ90 (AACQ3) | S2 | clause-manquante : devise posée à toute création, montant saisi ou non | sonde VER-001 |
| AACQ99 | AACQ90 | S2 | contrat d'abord (PACT10) des trois surfaces lues par les écrans | sonde VER-001 + lecteurs front calculés : 0 |
| AACQ100 | AACQ90 | S2 | clause-manquante : GET `/guardrail/` sans `ceiling_currency` | sonde VER-001 |
| AACQ101 | AACQ90 | S2 | clause-manquante : « (MAD) » en dur sur l'écran Connexion | lecture `ConnectionScreen.jsx` |
| AACQ102 | AACQ90 | S2 | clause-manquante : devise du seuil et motif bloqué jamais affichés | lecteurs front calculés : 0 |
| AACQ103 | AACQ26 | S3 | clause-manquante : CPL hors `cout_par_lead`, garde limitée à 4 fichiers | garde rejouée (exécutée) |
| AACQ104 | AACQ26 | S3 | clause-manquante : source du CPL jamais affichée (P3.5) | lecteurs front calculés : 0 |
| AACQ105 | AACQ68 | S3 | L5-test-affaibli : total et période précédente non affirmés | lecture du test |
| AACQ106 | AACQ10 | S3 | L5-test-affaibli : fenêtre jamais isolée du canal | lecture du test |

AACQ98 à AACQ102 découpent UN seul écart S2 (C-AACQ-VER-001) : une tâche par comportement, le contrat d'abord (AACQ99),
puis le serveur (AACQ98, AACQ100), puis les écrans qui portent `@after` sur leur moitié serveur (AACQ101, AACQ102). Les
tâches AACQ98-AACQ105 sont dans `docs/plans/PLAN_AUDIT_ACQUISITION.md` ; AACQ106 est dans `docs/plans/PLAN_AUDIT_LEAD.md`.

**Un écart S2, aucun S1. Pas de critique Fable**, puisqu'elle n'est due que si des S1 subsistent (METHODE §C.4.2).

## 5. Optionnel (hors correction ou spec, non déposé)

- **Lot 1.** `evaluate_creative_fatigue` appelle `record_anomaly`, qui n'a pas d'autre appelant.
- **Lot 1.** `ChantierImportScreen` n'affiche pas son erreur sous le champ fautif (règle maison « erreur sous le champ »).
- **Lot 1.** `rules_engine.py::_eval_cpl_band` se replie sur `s.cpl`.
- **AACQ38.** Le test-du-test décrit dans la tâche ne tue pas le mutant annoncé (garde morte) ; le test lui-même est juste.
- **AACQ60.** Séquencement PACT10 non respecté (même PR que les consommateurs) ; contenu juste, rien à corriger.
- **Rédaction.** `AdDetailScreen.jsx` l. 143 formate `cpl_odoo` en MAD (`formatMAD`), alors que le cockpit le formate dans
  la devise du compte (commentaire DATAPUB6 : la dépense est dans la devise du compte). Candidat S3, non sondé.
- **Rédaction.** Le delta budget du journal des règles (`RulesScreen.jsx` l. 634, « MAD/j ») porte des budgets Meta, donc
  dans la devise du compte, mais `rules_engine.py::_action_summary` ne sert pas cette devise. Candidat S3, non sondé.
- **CI.** Le run planifié « Release verify (full suite) » de `5ea32b58b` est en échec ; cause non examinée.

## 6. Couverture et non-couvert

- **Couvert.** 16 tâches sur 65 cochées (25 % tirées ; aucune P0 ou S1 cochée). Tous les commits et tous les tests nommés de
  l'échantillon ont été lus ; 1 sonde exécutée ; la garde AST d'AACQ26 rejouée.
- **Non couvert.**
  - Les 49 autres tâches cochées (hors échantillon).
  - Les preuves en direct (L7) de l'échantillon ne sont pas rejouées. Elles sont dans la dette gelée du groupe
    (`docs/audits/acceptation/AACQ/_dette.yml`, 50 ids, dont AACQ3, AACQ26 et AACQ68), et reviennent à l'orchestrateur du
    plan-run qui jouera l'acceptation AACQ89 (CLAUDE.md, étape 3-bis). Chaque tâche AACQ98-AACQ105 nomme son étape
    (P3.2 ou P3.5) pour ce rejeu.
  - Aucune nouvelle tâche `@acceptation` : AACQ89, ouverte, reste l'acceptation du groupe.
- **Statut du registre.** Il reste `audité` et ne passe pas `vérifié`, à cause de l'écart S2. Le groupe sort de la règle de
  sortie (METHODE §C.4.3) quand AACQ98-AACQ106 sont construites et qu'un second `vérifie` revient sans écart S1-S2.

## 7. Coût

- 3 vérificateurs opus : environ 0,56 M de jetons au total.
- Orchestrateur : préparation de la pile jetable, sonde, revue ; un rédacteur pour les tâches et ce dossier.
- Aucun appel Fable.

**Rejeu final (10/10, après intégration de `origin/main` du jour dans la branche de la PR).** la sonde AACQ rejouée(s) sur le code de la tête de branche : toutes REPRO, base inchangée à chaque rejeu isolé (les écarts de compte observés en rejeu groupé venaient d'écritures d'autres sessions sur la base de démo partagée).

<!-- verifie pct: 98 ecarts_s1_s2: 1 -->
