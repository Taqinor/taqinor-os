# Vérifie ACAL — contre-visite de clôture du groupe calepinage (D3), 10/10/2026

Commande « vérifie ACAL » (METHODE §C.4.2, skill audit §5). Le groupe compte **336 tâches cochées sur 351 constructibles**,
soit 95 % : la contre-visite de **clôture** (≥ 95 %) est due. Pour chaque tâche tirée, on rapproche le texte de la tâche, le
ou les commits et le test rouge nommé, avec les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart
S1-S2 est prouvé par une sonde exécutée en transaction annulée, ou par un rejeu vitest de l'atelier. Les écarts confirmés sont
déposés en tâches v3 dans le plan du propriétaire de leurs fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien écrit en production. Les seules actions sur la prod
sont des lectures, faites par l'orchestrateur et annoncées dans le chat (§3-bis).

## 0. Préconditions

- **SHA.** `origin/main` = `5ea32b58b` (PR #934). Branche de claim : `verifie-acal` (commit vide `a83af2aaa`).
- **Registre.** D3 `calepinage`, groupe ACAL, dossier `docs/audits/2026-10-04-calepinage.md`. Champ `statut` de
  `unites.yml` : `audité` (informatif) ; statut calculé par `audit_registre.py` : `construit` (336/351, 95 %).
- **Inventaire.** 352 tâches ACAL (ACAL1-352) dans 10 fichiers de plan. 16 restent ouvertes :
  - ACAL351 : l'acceptation live unique du groupe, jamais jouée ;
  - ACAL250 et ACAL275 : `[BLOCKED]` ;
  - 13 tâches d'autres propriétaires ou de nettoyage (ACAL251, 273, 274, 279, 280, 282, 284, 289, 311, 333, 334, 339, 347).
- **Échantillon (graine = SHA `5ea32b58b`).** 60 tâches cochées sont P0 ou S1, soit plus que le plafond de 48. On en a donc
  tiré **48 parmi les P0/S1**, et aucune dans le reste (276 tâches). Liste : ACAL2-5, 18, 22-24, 27-32, 34-38, 40, 44-46, 48,
  49, 51-54, 58-60, 62, 63, 90, 106, 145-148, 253, 260-264, 317, 318.
- **Pile pour les sondes.** Le partage de disque de Docker Desktop était cassé : le code monté en direct n'était pas fiable.
  Les sondes ont tourné dans un conteneur jetable `sonde-verifie` (image `erp-agentique-django_core`), avec le code de `main`
  copié par `git archive`, sur la base de démo `erp_db`. `showmigrations` : 0 migration en attente.
- **Vitest de l'atelier.** Worktree jetable à `56284c5e8` : `git diff 56284c5e8 5ea32b58b -- apps/web` est vide. Les
  `node_modules` sont reliés par jonction.

## 1. Vérificateurs (8 agents frais opus, effort élevé, lecture seule, même répertoire, + 1 vérificateur vitest opus)

| Lot | Tâches | ok | partiel | autre |
|---|---|---|---|---|
| 1 | ACAL2, 3, 4, 5, 18, 22 | 3 | ACAL18, ACAL22 | ACAL2 régression ultérieure (S4) |
| 2 | ACAL23, 24, 27, 28, 29, 30 | 3 | ACAL27, ACAL28, ACAL30 | — |
| 3 | ACAL31, 32, 34, 35, 36, 37 | 5 | ACAL32 | ACAL31 : soupçon réfuté par vitest |
| 4 | ACAL38, 40, 44, 45, 46, 48 | 5 | ACAL48 | — |
| 5 | ACAL49, 51, 52, 53, 54, 58 | 3 | ACAL49, ACAL51, ACAL54 | — |
| 6 | ACAL59, 60, 62, 63, 90, 106 | 3 | ACAL59, ACAL62, ACAL63 | ACAL62 reclassée par la critique |
| 7 | ACAL145, 146, 147, 148, 253, 260 | 4 | ACAL146, ACAL253 | — |
| 8 | ACAL261, 262, 263, 264, 317, 318 | 3 | ACAL262, ACAL264, ACAL317 | — |
| **Total** | **48** | **29** | **18** | **1 régression (ACAL2)** |

Points saillants des tâches jugées ok :

- **Six textes ont vieilli, pas le code** : ACAL5 (`lead_supprime`), ACAL44, ACAL45, ACAL145, ACAL147, ACAL263. Le code fait
  ce que la tâche voulait ; seul le texte décrit un état antérieur. Aucune tâche ouverte.
- **ACAL31.** Le vérificateur soupçonnait qu'un geste de production sans repavage rendait la production relue au lieu de la
  vivante. Le rejeu vitest (C1) le réfute : la production enregistrée suit bien la production vivante. Mais il montre une autre
  cause : la production vivante ne porte ni l'horizon ni l'ombrage (§3, écart C, ACAL356).
- **ACAL62 (reclassée).** Le vérificateur l'avait jugée ok. La critique Fable a montré qu'elle a le même trou qu'ACAL59 : le
  refus d'un module non résolu n'existe qu'à la création, pas à la resynchronisation (ACAL353).

## 2. Tests nommés rejoués

- **Django sur l'hôte (SimpleTestCase).** Les modules des lots 5 et 8 qui n'exigent pas de base ont été lancés sur l'hôte :
  tous verts. Le mutant du sérialiseur public d'ACAL51 (« lire `performance_ratio` sans condition ») a aussi été exécuté : il
  reste vert (§4, ACAL362).
- **Gardes.** `check_calepinage_cles_document.py` (garde ACAL343) : OK, avec sa dette gelée `exemple::modePoseDeclare`.
  `check_calepinage_actions_consommees.py` : OK. `check_api_shapes.py` : OK.
- **Le reste est raisonné.** Les tests Django à base de données des tâches échantillonnées n'ont pas été rejoués en local (la
  base de test partagée est réservée aux runs de plan). Ils sont couverts par le job `backend-tests` de la CI de `main` à
  `5ea32b58b`, qui est vert (la merge queue l'exige). Les écarts de ce dossier ne viennent pas de tests rouges : ils portent
  sur des clauses que ces tests verts n'exercent pas, et sont prouvés au §3.

## 3. Sondes (orchestrateur, conteneur jetable, transaction annulée, mail en mémoire, Celery coupé, HTTP sortant bloqué)

Les sondes sont committées dans `docs/audits/sondes/ACAL/`. Chacune expose `SONDE` (constat, SHA, attendu) et `sonde(ctx)`.

| Sonde | Tâche | Verdict | Sortie |
|---|---|---|---|
| `C-ACAL-VER-001.py` | ACAL59, ACAL62 | **REPRO** | « sync 200 panneaux 12->52 ttc 68900.00->178800.00 » : une surface au sol de 40 modules sans `moduleWc` est chiffrée au panneau 550 W au lieu d'être refusée. |
| `C-ACAL-VER-002.py` | ACAL63 | **REPRO** | « sync 200 panneaux {944: 12}->{944: 0} ttc 49700.00->16800.00 » : vers une fiche désignée non tarifée, l'ancienne ligne tombe à 0 et le devis répond 200. |
| `C-ACAL-VER-003.py` | ACAL22 | **REPRO** | « GET 200 empreinte=None ; section 400 {'base_empreinte': "Jeton manquant…"} » : un onglet ne peut pas écrire sa section sur un calepinage vierge. |
| `C-ACAL-VER-004.py` | ACAL253 | **REPRO en démo, sans impact en prod** | En démo : calepinage modifié True, `conception_divergente` False → True. En prod : voir §3-bis. |
| `C-ACAL-VER-005.py` | ACAL264 | **REPRO** | « pan B kWc [4.0] chaîné à Vmp/module [41.6], alerte=False » : un pan au module saisi est chaîné avec la fiche par défaut sans alerte. |

Note sur VER-002 : à la première exécution, le compteur global de la base est passé de 12 659 à 12 665. Ces 6 lignes
étaient des connexions `demo_admin` d'une autre session. La seconde exécution laisse la base inchangée, et aucun objet de
sonde ne reste. Toutes les sondes ont fini sur `ROLLED BACK`.

**Rejeu vitest de l'atelier (vérificateur opus).** Le fichier de rejeu n'est pas committé : ses tests A1, B1, C1 et C2 sont
repris tels quels comme « Test rouge d'abord » des tâches ACAL355, ACAL356 et ACAL357.

| Écart | Test | Verdict | Sortie |
|---|---|---|---|
| A (ACAL27) | A1 | **REPRO** | Exemple du contrat + une ombre tracée + matrice 0,8, puis « + Ajouter une zone » : `shadeObstructions` [shade-1, sh-1, sh-2] → [] et `shading12x24` → null. |
| B (ACAL28) | B1 | **REPRO** | A sud 6,6 kWc 11 220 kWh + B est 3,3 kWc 4 620 kWh, relu puis A retouché : `result.annualKwh` 16 500 au lieu de 15 840 (+660 kWh). |
| C (hors texte) | C1, C2, A2 | **REPRO** | Horizon 25° tout autour, ou matrice d'ombrage 0,8 relue : carte et `result.annualKwh` inchangés à 24 413 kWh. |
| Annexe | B1 | constat | L'exemple du contrat dit `result.kwc` 8,64 alors que ses zones font 14,4 kWc : relu, le prorata en tire 13 000 → 21 666 kWh. |

## 3-bis. Lectures en production (orchestrateur, lecture seule, 10/10)

- **ACAL253.** La migration `calepinage 0026` (pente racine → pan) est déjà appliquée. En prod : 5 calepinages, dont 1 lié à
  un devis, et 0 calepinage migré lié à un devis. Le cas reproduit en démo (une planche retirée du PDF d'un devis envoyé)
  n'a touché aucun devis réel. **Sans tâche.**
- **ACAL48 et ACAL54.** Les deux tâches demandaient une liste dry-run des simulations stockées avant merge. En prod : aucune
  simulation stockée, donc les listes sont vides. **Sans tâche.**

## 4. Écarts retenus

| Tâche | Écart de | Gravité | Cause | Preuve | Plan |
|---|---|---|---|---|---|
| ACAL353 | ACAL59, ACAL62 | S1 | L4-appelant (la resynchronisation ne lit pas les refus du document) | VER-001 | DEVIS |
| ACAL354 | ACAL63 | S1 | clause-manquante (fiche non tarifée = avertissement, puis ligne à 0) | VER-002 | DEVIS |
| ACAL355 | ACAL28 | S1 | clause-manquante (production par pan absente du document) | vitest B1 | CALEPINAGE |
| ACAL356 | hors texte (C-ACAL-VER-006) | S1 | L6-jumeau (`renderConfig` dérate, les rendus vivants non) | vitest C1, C2, A2 | CALEPINAGE |
| ACAL357 | ACAL27 | S2 | L6-jumeau (`addArea` passe par le vidage d'« Effacer ») | vitest A1 | CALEPINAGE |
| ACAL358 | ACAL264 | S2 | clause-manquante (pan sans fiche chaîné en silence) | VER-005 | CALEPINAGE |
| ACAL359 | ACAL264 | S3 | clause-manquante (écran : seul le module par défaut est montré) | lecture | CALEPINAGE |
| ACAL360 | ACAL22 | S3 | clause-manquante (jeton du document vide refusé) | VER-003 | CALEPINAGE |
| ACAL361 | ACAL32 | S3 | L5-test-affaibli (branche 201 jamais prise) | lecture | DEVIS |
| ACAL362 | ACAL51 | S3 | L5-test-affaibli (mutant du masquage vert, exécuté) | mutant | ANALYSE |
| ACAL363 | ACAL146 | S3 | clause-manquante (pas d'exemple GET au contrat) | lecture | CALEPINAGE |
| ACAL364 | ACAL317 | S3 | clause-manquante (écrivain gelé dans l'allowlist sans tâche) | garde | TRANSVERSE |
| ACAL365 | contrat | S3 | exemple du contrat contraire à la règle PV13 | vitest (annexe) | CALEPINAGE |

**6 écarts S1-S2** (ACAL353-358) et 7 S3. Les tâches sont au format v3, sous l'en-tête
`### ACAL — ÉCARTS vérifie 2026-10-10 · format v3` de chaque plan. ACAL364 va dans `PLAN_AUDIT_TRANSVERSE.md` parce qu'elle
touche `scripts/check_calepinage_ecrivains_layout.py` (propriétaire deploy) : sa garde échoue sur une entrée d'allowlist
morte, donc l'écran et l'allowlist doivent changer dans le même commit.

Les chiffres que voit le client : ACAL355 et ACAL356 changent la production imprimée, mais **seulement sur les nouveaux
rendus**. Aucun document stocké n'est réécrit, et un devis envoyé garde ce que le client a reçu (règle du 08/10). ACAL356
renvoie à D-ACAL-6 : la production vue par le client est celle du devis, qui devient cohérente avec l'étude.

**Aucune nouvelle tâche d'acceptation.** ACAL351 (ouverte) reste l'acceptation unique du groupe ; chaque tâche nomme son
étape du parcours PA2 (`apps/calepinage/parcours/PA2.json`).

## 4-bis. Critique Fable (1 appel, une seule passe sur l'ensemble des verdicts)

- **Confirmé** : les écarts S1 de la resynchronisation (VER-001, VER-002) et de la production par pan (B1).
- **Reclassé** : ACAL62, de ok à partiel. Même trou qu'ACAL59 : le refus d'un module absent de `modules[]` n'est lu qu'à la
  création. Les deux sont réunis dans ACAL353.
- **Tranché** : le dérate absent de la production vivante est un **S1** à déposer (chiffre client plus optimiste que l'étude
  serveur) → ACAL356, constat C-ACAL-VER-006.
- Apport net : 1 écart S1 qui n'était dans le texte d'aucune tâche, et 1 tâche « ok » corrigée.

## 5. Optionnel (hors correction ou spec, non déposé)

- **ACAL2.** CIQ112 (`4c6139fd2`) a ajouté `modePoseDeclare` au schéma `roof_layout_v2` sans l'ajouter à l'exemple. La dette
  est gelée dans `scripts/cles_document_sans_ecrivain_allow.txt` (propriétaire deploy). Régression ultérieure, S4.
- **ACAL18.** L'exemple `exemple_roof_layout_riche` de `proposal_data.json` (2 copies) porte des valeurs que le serveur
  supprime (`family: 'residentiel'`, `face: 'sud'`, `mode: 'auto'`, origine en chaîne). Le test ne compare que les clés. S4.
- **ACAL30.** La mention `MENTION_PRODUIT_ARCHIVE` n'a aucun lecteur ; `zones.ts::syncModulePicker` affiche son propre texte
  « ne figure plus ». S4.
- **ACAL49.** `par_pan` est `null` sans motif par pan (`services/chaine_pertes.py::_bloc_production`, clés `*_motif`
  absentes à l'exécution). S4.
- **ACAL262.** `angleDeg` n'est pas rendu par `scene3d.ts`, et le visualiseur public (`viewerOnly`,
  `lib/proposition.ts::buildViewerModel`) garde des cotes fixes. S4.
- **ACAL44.** Le test du 409 passe aussi sur l'ancien code (non discriminant), mais le comportement livré est juste.
- **ACAL46.** La revérification en prod du dry-run n'est pas tracée dans le DONE LOG.

## 6. Couverture et non-couvert

- **Couvert.** 48 tâches sur 336 cochées, toutes tirées parmi les 60 P0/S1. Tous les commits ont été lus, les tests nommés
  ont été lus, et ceux qui tournent sans base ont été rejoués. 5 sondes Django et 1 rejeu vitest ont été exécutés.
- **Non couvert.**
  - Les 288 autres tâches cochées, dont 12 P0/S1 non tirées (plafond de 48).
  - Les tests Django à base de données : raisonnés et couverts par la CI de `main`, pas rejoués en local (§2).
  - L'acceptation live du groupe : ACAL351 reste ouverte et n'a jamais été jouée. La dette gelée
    `docs/audits/acceptation/ACAL/_dette.yml` compte 287 tâches cochées à preuve en direct sans enregistrement. Les preuves en
    direct (L7) ne sont donc pas rejouées ici : elles reviennent à l'orchestrateur du plan-run qui jouera ACAL351
    (CLAUDE.md, étape 3-bis).
- **Statut du registre.** Il reste `construit` et ne passe pas `vérifié`, à cause des 6 écarts S1-S2. Le groupe sort du cycle
  (METHODE §C.4.3) quand ACAL353-358 sont construites et que deux `vérifie` consécutifs reviennent sans écart S1-S2.

## 7. Coût

- 8 vérificateurs opus (effort élevé) : environ 1,9 M de jetons au total.
- 1 vérificateur vitest opus : environ 0,26 M de jetons.
- 1 appel Fable (critique des verdicts, §4-bis).
- Orchestrateur : sondes, lectures prod, rejeu des gardes, rédaction.

<!-- verifie pct: 95 ecarts_s1_s2: 6 -->
