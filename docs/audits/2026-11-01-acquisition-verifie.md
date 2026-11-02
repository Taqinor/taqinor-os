# Vérifie AACQ — deuxième contre-visite de clôture du groupe acquisition (J0), 01/11/2026

Commande `vérifie AACQ` (METHODE §C.4.2, skill audit §5), lancée par la session d'orchestration du `loop audit` du 01/11.
Le groupe compte **75 tâches cochées sur 75** constructibles. Les neuf tâches ÉCART de la contre-visite du 10/10
(`docs/audits/2026-10-10-acquisition-verifie.md`, AACQ98-106) sont cochées.

`audit_registre.py --du` ne la liste pas : sa règle ignore la contre-visite qui suit le drainage des écarts. Le groupe ne
sort du cycle qu'après deux contre-visites consécutives sans écart S1-S2 ; celle-ci est donc due.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main`, avec
les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée
en transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire.

La contre-visite n'a rien construit. Elle n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.**
  - Échantillon et vérificateurs : `origin/main` = `c6ab9b58e` (PR #1198).
  - Rédaction : `origin/main` = `4b248575c`. Les commits intermédiaires ne touchent que `docs/` (contre-visites
    parallèles) ; `apps/adsengine`, `apps/crm` et `apps/web` sont inchangés.
  - Branche : `verifie-aacq-0111`.
- **Inventaire (déterministe).** 75 tâches AACQ `[x]` dans les plans actifs. Le script de tirage est le même que pour
  ASTK et ACHT : les P0/S1, toutes les tâches ÉCART du 10/10, puis 25 % du reste par `random.Random(int(sha, 16)).sample`.
- **Échantillon (graine = `c6ab9b58e`), 27 tâches.**
  - **Imposées (10)** : AACQ41, AACQ98-106.
  - **Tirées (17)** : AACQ12, 16, 24, 26, 31, 36, 42, 61, 63, 65, 67, 70, 72, 76, 77, 95, 96.
- **Pile des sondes.**
  - Conteneur partagé `erp-agentique-django_core-1`, sur le code de `main`.
  - Les sondes passent une à une par le verrou commun.
  - Chaque sonde tourne en transaction annulée.
  - Le moteur Docker, tombé pendant la contre-visite, a été redémarré par le fondateur ; les sondes ont été jouées après.

## 1. Vérificateurs (3 agents frais, opus, effort élevé, lecture seule, même répertoire, 9 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **27** | toutes ; texte vieilli : AACQ31 (la synchro Odoo ne fait plus que signaler depuis AACQ97), AACQ76 (migration 0059 et non 0058) |
| partiel / non-fait / faux / régression / déjà-présent | 0 | — |

**Preuves exécutées par les vérificateurs.**
- Garde AST d'AACQ26/AACQ103 rejouée sur les 131 fichiers non-test d'`apps/adsengine` : 0 division hors de
  `cout_par_lead`.
- `scripts/check_adsengine_ecrans.py` : « OK — 0 site(s) historique(s) gelé(s) ».
- `scripts.tests.test_check_adsengine_ecrans` : 6 tests OK.

**Les écarts du 10/10 tiennent sur `main`.** AACQ98-106 sont ok, avec acceptation en direct
`docs/audits/acceptation/AACQ/2026-10-11-cf66024bc.md` (PASS). La sonde C-AACQ-VER-001 est réfutée.

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (code de `main`, transaction annulée) |
|---|---|---|---|
| `C-AACQ-VER-001.py` (10/10) | AACQ98, AACQ100 | réfuté | « règle 201 devise='' seuil_par_défaut=250 applicable=False ; garde-fou PATCH 200 devise_base='USD' devise_exposée_GET=True » |
| `C-AACQ-VER-301.py` | hors texte d'AACQ98 | **REPRO** | « GET0 plafond=100 devise='' ; PATCH même valeur 200 -> devise='' ; PATCH plancher seul 200 -> devise='USD' plafond_quotidien=100 » |

## 3. Écarts retenus (déposés dans `docs/plans/PLAN_AUDIT_ACQUISITION.md`, section « AACQ — ÉCARTS vérifie 2026-11-01 »)

| Tâche | Écart de | Grav. | Cause | Preuve |
|---|---|---|---|---|
| AACQ107 | AACQ98 (hors de son texte) | **S2** | clause manquante | sonde VER-301 |
| AACQ108 | AACQ102 (hors de son périmètre) | S3 | clause manquante | lecture |

**AACQ107.** Sur un compte Meta en USD, l'écran Connexion demande de « ressaisir » le plafond. Ressaisir la même valeur ne
pose pas la devise : le plafond reste inopérant et l'alerte ne disparaît jamais. À l'inverse, changer le seul plancher
estampille « USD » sur tous les plafonds, dont celui par défaut qui n'a jamais été ressaisi.

**AACQ108.** Le message `blocked_fr` d'une règle monétaire demande de ressaisir le seuil. Aucun écran n'écrit
`params.threshold_mad` (`RulesScreen.jsx` n'envoie que `{enabled, dry_run}`). Sur un compte non-MAD, ces règles restent
donc inapplicables.

**Constats S1-S2 : 1**, reproduit par sonde. Aucun S1 : pas de seconde lentille ni de critique Fable. Aucune tâche cochée
n'est fausse : l'écart S2 vient d'une clause qu'AACQ98 n'avait pas écrite. Il compte pourtant comme écart S1-S2 du groupe
pour la sortie du cycle (METHODE §C.4.3).

## 4. Optionnel (hors correction ou spec, non déposé)

- **AACQ16.** La migration 0058 ajoute `budget_type` sans backfill. Un ad set à budget global synchronisé avant 0058 peut
  être dupliqué en budget quotidien jusqu'au prochain `sync_adsets`. Le plafond quotidien s'applique quand même.
- **AACQ12.** Le test utilise des utilisateurs synthétiques porteurs de MANAGE plutôt que les rôles Technicien et
  Commercial seedés.
- **Garde AACQ77.** La règle R1 exempte toute une fonction dès qu'elle contient `fetchAllPages`, et ne voit pas un
  `r.data` nu.
- **AACQ67.**
  - Réouvrir puis enregistrer sans rien changer réécrit `tested_variable` vide, mais seulement par une voie sans appelant
    de production.
  - `loadSavedPlan` avale ses erreurs (`.catch(() => {})`).
- **AACQ65.** La vérification et l'écriture du verdict de `conclure` se font sans verrou. Le second appel est un no-op
  idempotent.
- **AACQ70.** `backfill_complet` répond 202 sans connexion Meta active.
- **Devise affichée en dur.**
  - `ConnectionScreen.jsx` affiche « 100 USD » à côté de l'alerte « saisi en MAD ».
  - `AdDetailScreen.jsx` formate `cpl_odoo` en MAD.
  - Le delta du journal de `RulesScreen.jsx` est écrit « MAD/j ».
- **Données antérieures.** Les règles et garde-fous estampillés « USD » entre AACQ3 et AACQ98 sur un compte non-MAD n'ont
  pas été réparés. Cela ne compte que si la production a une `MetaConnection` non-MAD, ce qui n'a pas été vérifié (prod
  non lue).

## 6. Couverture et non-couvert

- **Couvert.**
  - 27 tâches sur 75 cochées, avec leurs commits et leurs tests nommés lus.
  - Deux sondes jouées sur le code de `main`.
- **Non couvert.**
  - Les 48 autres tâches cochées.
  - Aucun test Django ni vitest exécuté par les vérificateurs. Leur vert est celui de la CI de `main`.
  - Aucun rejeu à l'écran.
- **Statut du registre.** Après ce dépôt : 75 cochées sur 77 constructibles (AACQ107-108 ajoutées). Contre-visite avec
  **1 écart S1-S2** : le cycle n'est pas sorti.

## 7. Coût

- 3 vérificateurs opus (effort élevé) : ≈ 0,61 M de jetons.
- 1 rédacteur opus : 2 tâches v3.
- Orchestrateur : tirage, rejeu de 2 sondes, triage, rédaction.
- H0 S0 O4 F0

<!-- verifie | groupe: AACQ | pct: 100 | ecarts_s1_s2: 1 -->
