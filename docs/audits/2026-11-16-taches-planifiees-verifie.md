<!-- verifie | groupe: ACEL | pct: 97 | ecarts_s1_s2: 1 -->

# Vérifie ACEL — 5e contre-visite des correctifs du parcours PF11 « tâches planifiées », 16/11/2026

Déclencheur : `audit_registre.py --du` (« vérifie dû, contre-visite des correctifs », 66/68 = 97 %). Périmètre ÉTROIT
(§C.4.6) : la tâche d'écart déposée par la 4e passe (ACEL100, PR #1426) et la tâche du constat S2 d'origine encore ouverte
(ACEL1 / C-ACEL-001), avec son nœud de dépendances ACEL1 / ACEL31 / ACEL4. Cette passe ne remplace aucune passe du 15/11
(nouvelle date). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `daed8f767` (merge de la PR #1426). ACEL100 : commit `5b4764399`, coche `707168ddd`.
  Branche : `verifie-acel-1611`.
- **Registre.** 66 cochées sur 68 ; ouvertes : ACEL1, ACEL9 ; bloquées « code livré, preuve en direct due » : ACEL3, ACEL4,
  ACEL8, ACEL13, ACEL31, ACEL36, ACEL42, ACEL46.
- **Méthode.** Code et test sur `origin/main`, appelants lus (grep `_parse_rows`, `__parse_error__`) ; corps réel de
  `_parse_rows` extrait par ast et exécuté sur l'hôte ; mutant par retrait du `isinstance`. Sonde 001 rejouée sur le vrai
  `celery.py` et sur deux variantes en mémoire du planning. Aucune pile, aucun test Django, aucun worker, aucune production.

## 1. Verdicts

| Tâche | Constat d'origine | Verdict | Motif |
|---|---|---|---|
| ACEL100 | C-ACEL-VER6-600 (S3) | **ok** | toute valeur JSON non-objet devient une ligne en erreur « objet JSON attendu » ; mutant rouge |
| ACEL1 | C-ACEL-001 (S2) | **non-fait** (ouverte, inconstructible) | planning toujours `crontab(hour=6, minute=0)` ; sonde 001 `repro: true` ; refusée par `plan_lanes` (cycle) |
| ACEL31 | C-ACEL-001 (S2) | bloquée (preuve due) | code sur `main` (`_deja_journalise_ce_jour`) ; preuve = sonde rejouée APRÈS ACEL1 |
| ACEL4 | C-ACEL-007, 022 (S3) | bloquée (preuve due) | code sur `main` (`celery.py::_expire_dans`) ; preuve = pile avec worker arrêté et beat |

## 2. ACEL100 en détail

- **Code.** `publicapi/bulk.py::_parse_rows`, branche `jsonl` : la valeur lue est gardée si c'est un `dict`, sinon remplacée
  par `{'__parse_error__': 'objet JSON attendu'}` ; une ligne illisible garde son message d'origine. 2 lignes nettes.
  La branche CSV (`csv.DictReader`) ne rend que des `dict` : inchangée.
- **Appelants.** `_parse_rows` de `publicapi` n'a qu'un appelant (`run_import_job`) ; l'homonyme de
  `ventes/paiement_import.py` est une autre fonction. `run_import_job` traite `__parse_error__` en ligne en erreur avant
  tout `row.get` métier.
- **Rejeu hôte (corps réel).** Lignes `[1, 2]`, `5`, `null`, `"txt"`, `true` entre deux objets : trois lignes, toutes des
  `dict`, la ligne 2 en erreur « objet JSON attendu ». `{}` reste un objet (validé ensuite comme ligne en erreur métier).
  CSV à colonne en trop (clé `None`) : `dict`, traité sous le `except Exception` de ligne. Mutant sans `isinstance` : la
  liste sort telle quelle, `row.get` lèverait `AttributeError` comme avant.
- **Test** (`tests_aana_reprise_bulk.py::RepriseBulkTest::test_ligne_jsonl_non_objet_n_arrete_pas_les_suivantes`) : vrai
  `run_import_job`, fichier A / `[1, 2]` / C ⇒ `termine`, curseur 3, `erreurs = 1`, journal ligne 2 « objet JSON attendu »,
  importés A et C. Il lève si le correctif saute. Non exécuté ici : la seule preuve d'un vert est la CI de la PR #1426.
- **Verdict de l'énumération** (tableau du 15/11, §3) : la ligne « boucle : `row.get` sur valeur JSON non-objet » est
  fermée. Aucun contenu de fichier ne laisse plus un job `en_file` ni `en_cours` ; restent les S4 du 15/11 (VER6-601, 602).

## 3. ACEL1 : nœud de dépendances et plage horaire, amendés sur place

- **Cycle prouvé.** `plan_lanes.py docs/plans/PLAN_AUDIT_DEPLOY.md` (rejoué) : « REFUSÉ (@after externe, OWN) : ACEL1 —
  attend ACEL31 … attend ACEL4 ». ACEL31 et ACEL4 sont bloquées sur leur preuve en direct, et celle d'ACEL31 est « sonde
  rejouée APRÈS la moitié planning », c'est-à-dire après ACEL1 : aucune des trois ne peut avancer. Le code des deux
  prérequis est sur `main` depuis le 13/11 ; l'`@after` n'a plus d'objet.
- **Plage horaire prouvée** (C-ACEL-VER7-700, S3). Sonde 001 sur le planning qu'ACEL1 demandait (`crontab(minute=0)`, 0-23 h) :
  7, 8, 9 h partent à l'heure, mais un rapport sans heure part à 00:00 et un rapport réglé à 3 h part à 3 h, alors que
  l'écran (`EnvoisProgrammesPage.jsx`) dit « Vide : 6 h ; de 0 à 5 h, part à 6 h ». Avec `hour='6-23'` : 7, 8, 9 h à l'heure,
  3 h et vide à 6 h, un seul envoi par jour. C'est l'ancien VER5-503 (S4), désormais prouvé.
- **Amendement** (METHODE §C.2-7, exception étroite ajoutée dans cette PR). Dans la ligne d'ACEL1 : `@after` retiré ; Given
  réécrite sur le code d'ACEL31 sur `main` ; « fini quand » et code net en `crontab(minute=0, hour='6-23')` ; test
  `set(range(6, 24))` et second mutant (sans `hour`) ; preuve en direct sur la sonde 001 mise à jour. Identifiant, priorité,
  fichiers et modèle inchangés. Après ce merge, `plan_lanes` rend ACEL1 constructible ; la preuve d'ACEL31 suit.

## 4. Sonde 001 mise à jour

`docs/audits/sondes/ACEL/C-ACEL-001.py` : lit les plages « a-b » du champ `hour` ; remplace le `_deja_journalise_ce_jour`
d'ACEL31 (lecture de la base) par un journal du jour en mémoire, sans quoi elle levait `NameError` dès qu'un passage horaire
atteint l'heure réglée ; ajoute les cas 3 h et vide, et les sorties « plus_d_un_envoi_par_jour » et
« conforme_a_l_ecran_3h_et_vide_a_6h ». `repro` garde son sens (7, 8 ou 9 h jamais dû). Rejouée : `main` ⇒ `repro: true` ;
`6-23` ⇒ `repro: false`, écran conforme ; `0-23` ⇒ `repro: false`, écran non conforme.

## 5. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Preuve | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER7-700 | ACEL1 | S3 | la plage 0-23 h demandée par ACEL1 enverrait les rapports sans heure à minuit, contre l'écran | sonde 001 (hôte) | ACEL1 amendée |
| C-ACEL-VER7-701 | ACEL1 ↔ ACEL31 | S3 | cycle `@after` / preuve : ACEL1 refusée par `plan_lanes`, ACEL31 bloquée sur elle | `plan_lanes` | ACEL1 amendée |

Aucune tâche nouvelle. Les S4 du 15/11 (VER5-504, VER6-601, 602, 603) restent optionnels.

## 6. Couverture et sortie de cycle

- **Couvert.** ACEL100 : code, commit, test nommé, appelants, mutant hôte ; ACEL1 / ACEL31 / ACEL4 : planning, `plan_lanes`,
  sonde 001 sur trois plannings.
- **Non couvert sans pile.** Aucun test Django lancé ; preuves en direct d'ACEL31 et ACEL4 ; sondes 002-004 non rejouées
  (état du 15/11 : 002 plante, 003 inconclusive, 004 périmée).
- **Constats d'origine.** C-ACEL-VER6-600 : **fermé**. C-ACEL-001 (S2) : **non fermé** (ACEL1 ouverte, sonde `repro: true`).
- **Statut.** Aucun écart S1-S2 nouveau. Le marqueur compte 1 : C-ACEL-001 (§C.4.6). Le groupe reste « construit ».
  Sortie de cycle : 0 `vérifie` consécutif à zéro S1-S2. Prochaine contre-visite utile : après le build d'ACEL1.

## 7. Coût

- H0 S0 O1 F0 · jetons sous-agents ≈ 0 M — l'orchestrateur seul (opus) ; aucun appel Fable, aucun sous-agent.
