# Vérifie ACHT — deuxième contre-visite de clôture du groupe chantiers (J2), 01/11/2026

Commande `vérifie ACHT` (METHODE §C.4.2, skill audit §5), lancée par la session d'orchestration du `loop audit` du 01/11.
Le groupe compte **108 tâches cochées sur 108** constructibles. Les onze tâches ÉCART de la contre-visite du 30/10
(`docs/audits/2026-10-30-chantiers-verifie.md`, ACHT113-123) sont cochées.

`audit_registre.py --du` ne liste pas cette contre-visite : sa règle ignore celle qui suit le drainage des écarts. Le
groupe ne sort du cycle qu'après deux contre-visites consécutives sans écart S1-S2 ; celle-ci est donc due.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main` avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit. Elle n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon et vérificateurs : `origin/main` = `c6ab9b58e` (PR #1198). À la rédaction, `origin/main` =
  `85c2643e0`. Ce diff ne touche que des fichiers `docs/` (contre-visites AMOT, APAR, ADOC). Branche : `verifie-acht-0111`.
- **Inventaire (déterministe).** 108 tâches ACHT `[x]` dans les plans actifs. Le même script que pour ASTK tire :
  - les P0 et S1 ;
  - toutes les tâches ÉCART du 30/10 ;
  - 25 % du reste, par `random.Random(int(sha, 16)).sample` sur les identifiants triés.
- **Échantillon (graine = `c6ab9b58e`), 41 tâches.**
  - **Imposées (18).** ACHT1, 2, 3, 44, 52, 53, 99 et ACHT113-123.
  - **Tirées (23).** ACHT9, 11, 14, 22, 27, 30, 33, 34, 39, 46, 49, 51, 57, 59, 62, 69, 71, 74, 91, 102, 105, 107, 112.
- **Pile des sondes.** Conteneur partagé `erp-agentique-django_core-1`, sur le checkout principal à `c6ab9b58e`.
  - Les sondes passent une à une par le verrou commun à deux places.
  - Elles tournent en transaction annulée : base inchangée à chaque rejeu.
  - Le moteur Docker est tombé pendant la vérification, puis a été redémarré par le fondateur. Les vérificateurs ont donc
    lu le code sans exécuter, et l'orchestrateur a rejoué ensuite toutes les sondes.

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire, ≈ 10 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **32** | ACHT1, 2, 3, 9, 11, 14, 22, 27, 30, 34, 44, 49, 51, 52, 57, 62, 71, 74, 91, 102, 105, 107, 112, 113-121 |
| partiel | **9** | ACHT33 (S2), ACHT46 (S2), ACHT39, 53, 59, 69, 99, 122, 123 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Changements postérieurs jugés voulus.**
- Refus passés de 400 à 409 (ERR-ENF11 : ACHT2, 11, 34, 49, 74).
- Identifiant d'une autre société → 404 (fuzz #997 : ACHT44).
- Fichiers de tests regroupés par APRF37 (ACHT62).
- ACHT118 a réécrit `test_recul_reste_permis` selon la règle voulue (recul d'un seul rang).

**Les écarts du 30/10 tiennent sur `main`.** ACHT113-121 sont ok, avec preuve en direct (enregistrement
`docs/audits/acceptation/ACHT/2026-10-30-2f9b24150.md`, E1-E8, E10).

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (code de `main`, transaction annulée) |
|---|---|---|---|
| `C-ACHT-VER-004.py` (30/10) | ACHT113 | REPRO, attendu | POST `mise-en-service` sur chantier Réceptionné **200**. Le geste serveur était juste ; le correctif ACHT113 porte sur l'écran (vitest + étape E1). |
| `C-ACHT-VER-005.py` (30/10) | ACHT114 | réfuté | « acc2=200 chantiers=1 annule=False bom2={…: 14.0} » |
| `C-ACHT-VER-006.py` (30/10) | ACHT115 | REPRO, attendu | le serveur refuse toujours `conforme` (400 « pass, fail ou en_attente »). Le correctif ACHT115 envoie `pass`/`fail` depuis l'écran (vitest + E3). |
| `C-ACHT-VER-007.py` (30/10) | ACHT116 | réfuté | « patch=[200, 200, 200] … ApiEvent intervention.completed=1 » |
| `C-ACHT-VER-008.py` (30/10) | ACHT117 | REPRO, attendu | un corps sans `motif` → 409 par conception ; l'écran demande désormais le motif (vitest + E4) |
| `C-ACHT-VER-101.py` | ACHT33 | **REPRO** | « témoin(base_updated_at) status=conflit ligne=12.00 ; écran(sans base) status=applied ligne=8.00 (en ligne: 12) » |
| `C-ACHT-VER-201.py` | ACHT46 | **REPRO** | « ORDRE A [(False,'2026-10-12','2036-10-12'),(True,'2026-10-12','2036-10-12')] ORDRE B [(False,'2026-10-12','2036-10-12'),(True,'2026-10-05','2036-10-05')] » |

Les sondes 004, 006 et 008 rejouent le comportement serveur du 30/10, qui reste voulu : les trois correctifs sont côté
écran.

L'orchestrateur a corrigé la sonde VER-101 avant son verdict, sans changer son attendu. Elle créait une ligne de
consommation que `ensure_consommation` retirait (ligne hors nomenclature non marquée).

## 3. Écarts retenus

| Tâche | Écart de | Grav. | Cause | Preuve | Plan |
|---|---|---|---|---|---|
| ACHT124 | ACHT33 | **S2** | L4, appelants oubliés : aucun appelant de production ne transmet `baseUpdatedAt`. Une correction de consommation mise en file hors ligne écrase en silence une correction en ligne plus récente. | sonde VER-101 | `PLAN_AUDIT_CHANTIERS.md` |
| ACHT125 | ACHT46 | **S2** | L5 + clause partielle : une série relevée avant la réception garde la date de pose du terrain. Parc et fin de garantie dépendent de l'ordre relevé / réception. | sonde VER-201 | `PLAN_AUDIT_SAV.md` |
| ACHT126 | ACHT59 | S3 | L3 : le vrai 409 cite `motif_override_signature`, et le faux serveur du test sert un autre corps | lecture | `PLAN_AUDIT_CHANTIERS.md` |
| ACHT127 | ACHT39 | S3 | clause manquante : une pose peut démarrer un samedi ou un dimanche | lecture | `PLAN_AUDIT_CHANTIERS.md` |
| ACHT128 | ACHT69 | S3 | clause manquante face à la décision fondateur : un 500 est marqué sans réessai, et un 503 persistant n'est jamais montré | lecture | `PLAN_AUDIT_DEPLOY.md` |
| ACHT129 | ACHT122 | S3 | L7 : séries et lot absents du détail de la réception, alors que l'enregistrement d'acceptation dit PASS | lecture | `PLAN_AUDIT_STOCK.md` |

**Constats S1-S2 : 2**, reproduits par sonde. Aucun S1, donc ni seconde lentille ni critique Fable.

**Sans nouvelle tâche.**
- ACHT99 et ACHT123 : l'oracle `audit_coherence` est relâché à « 0 violation sur les objets du rejeu » (154 violations
  préexistantes sur la base de démo), et le rejeu a tourné avec un `EMAIL_BACKEND` anymail à clé invalide. Déjà relevé le
  30/10 ; c'est une hygiène d'acceptation, à trancher par l'orchestrateur du prochain rejeu.
- ACHT53 : test sans rejeu en base, déjà rangé en optionnel le 30/10.

## 4. Optionnel (hors correction ou spec, non déposé)

- ACHT30 / ACHT34 : `ajouter-serial`, `ajouter-reserve` et la signature en ligne n'ont pas la garde « validée / annulée »
  de la synchro.
- ACHT2 : un POST `mise-en-service` sur un chantier annulé déjà Réceptionné passe la garde (même statut canonique).
- ACHT105 : le toast « Voir le chantier » n'a pas de test. Le jumeau `SigneDialog.jsx::confirmer` n'a ni toast ni lien.
- ACHT62 : l'historique de `SuiviGpsPage.jsx` ne lit qu'une page (`page_size` 200).
- ACHT74 : un PATCH direct de `date_derniere_calibration` n'est pas borné.
- ACHT46 : `sav/services.py::ensure_equipement_for_bom_line` n'a plus d'appelant.
- ACHT49 : le rapport énergie affiche un message générique au lieu de la raison du 400/409.
- ACHT119 : `_exiger_nomenclature` passe avant le verrou dans `terminer` (fenêtre étroite).
- ACHT122 : le serveur ne dédoublonne pas la liste des séries.

## 6. Couverture et non-couvert

- **Couvert.** 41 tâches sur 108 cochées. Commits et tests nommés lus. Sept sondes jouées sur le code de `main`.
- **Non couvert.**
  - Les 67 autres tâches cochées.
  - Aucun vitest ni test Django exécuté par les vérificateurs (worktree sans `node_modules`, pile en panne pendant leur
    lecture). Leur vert est celui de la CI de `main`.
  - Aucun rejeu à l'écran.
- **Statut du registre.** Après ce dépôt : 108 cochées sur 114 constructibles (ACHT124-129 ajoutées). La contre-visite
  compte **2 écarts S1-S2** ; le cycle n'est pas sorti.

## 7. Coût

- 4 vérificateurs opus (effort élevé) : environ 0,87 M de jetons.
- 1 rédacteur opus : 6 tâches v3.
- Orchestrateur : tirage, rejeu sériel de 7 sondes (dont 1 corrigée), triage, rédaction.
- H0 S0 O5 F0

<!-- verifie | groupe: ACHT | pct: 100 | ecarts_s1_s2: 2 -->
