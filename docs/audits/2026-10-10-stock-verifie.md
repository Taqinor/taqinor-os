# Vérifie ASTK — contre-visite de clôture du groupe stock (J3), 10/10/2026

Commande « vérifie ASTK » (METHODE §C.4.2, skill audit §5). Le groupe compte **183 tâches cochées sur 189** constructibles,
soit 96 % : la contre-visite de **clôture** (≥ 95 %) est due. C'est la deuxième contre-visite du groupe, après celle du
09/10 (`docs/audits/2026-10-09-stock-verifie.md`) : ses 17 `ERR-ASTK*` sont cochés dans `docs/ERROR_PLAN.md` (le GATED ERR-ASTK63 reste ouvert) ; la section « ÉCARTS vérifie 2026-10-09 » de `PLAN_AUDIT_STOCK.md` porte ASTK240-243.

Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou les commits et le test rouge nommé, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `5ea32b58b` (PR #934). Branche de claim : `verifie-astk` (commit vide `a858b82c3`, présente sur
  `origin`). CI de `main` à `5ea32b58b` : « CI » vert en `push` et en `merge_group` ; semgrep et bandit verts. Le run
  planifié « Release verify (full suite) » de ce commit est rouge : non examiné ici (hors stock, voir §6).
- **Fraîcheur.** Au moment de la rédaction, `origin/main` = `8d48382d2` (27 commits de plus). Ce diff ne touche aucun fichier
  cité ici (`apps/stock`, `facturation_ops.py`, `bon_commande.py`, `installations/services.py`, `frontend/src/pages/stock`),
  seulement une ligne de DONE LOG de `PLAN_AUDIT_FACTURATION.md`.
- **Registre.** J3 `stock`, groupe ASTK, statut calculé `construit` (`audit_registre.py status` : 183/189, 96 %, dernière
  contre-visite le 09/10 avec écarts S1-S2). Plans alimentés : STOCK, CHANTIERS, DEPLOY, DEVIS, FACTURATION, SECURITE, ANALYSE,
  TRANSVERSE, DOCUMENTS.
- **Inventaire (déterministe).** 189 tâches ASTK constructibles, 183 `[x]`. Les 6 restantes :
  - ASTK210 et ASTK211 : `[BLOCKED: hors périmètre]` ;
  - ASTK239 : acceptation en direct du groupe, jamais jouée ;
  - ASTK240, ASTK241, ASTK243 : écarts de la contre-visite du 09/10, ouverts.
- **Échantillon (graine = SHA `5ea32b58b`).** Toutes les P0 et S1 (30), plus 25 % du reste tiré par la graine (18 sur 153).
  Total : **48 tâches**. Par fichier : STOCK 40, CHANTIERS 4, DEPLOY 1, ANALYSE 1, FACTURATION 1, DEVIS 1.
- **Pile des sondes.** Conteneur jetable `sonde-verifie` sur l'image `erp-agentique-django_core`, avec le code de `main`
  copié par `git archive` (le partage de disque de Docker Desktop était cassé : le code monté en direct n'était pas lisible).
  Base `erp_db` de démo, 0 migration en attente. Chaque sonde tourne dans une transaction annulée ; aucune donnée ne reste.

## 1. Vérificateurs (8 agents frais, opus, effort élevé, lecture seule, même répertoire, 6 tâches chacun)

| Lot | Tâches | ok | partiel | Hors lot relevé |
|---|---|---|---|---|
| 1 | ASTK1, ASTK2, ASTK3, ASTK4, ASTK5, ASTK6 | 6 | — | — |
| 2 | ASTK7, ASTK8, ASTK9, ASTK15, ASTK17, ASTK18 | 6 | — | acomptes fournisseur lisibles sans `prix_achat_voir` (→ C-ASTK-VER-003) |
| 3 | ASTK28, ASTK32, ASTK33, ASTK34, ASTK37, ASTK38 | 5 | ASTK33 | — |
| 4 | ASTK39, ASTK40, ASTK41, ASTK42, ASTK43, ASTK44 | 6 | — | — |
| 5 | ASTK51, ASTK59, ASTK60, ASTK81, ASTK82, ASTK83 | 4 | ASTK59, ASTK83 | — |
| 6 | ASTK84, ASTK87, ASTK95, ASTK98, ASTK108, ASTK109 | 5 | ASTK87 | — |
| 7 | ASTK120, ASTK121, ASTK129, ASTK135, ASTK140, ASTK180 | 5 | ASTK180 | livrer-partiel puis facture = double sortie (→ C-ASTK-VER-001) |
| 8 | ASTK199, ASTK205, ASTK213, ASTK216, ASTK220, ASTK242 | 4 | ASTK199, ASTK242 | — |
| **Total** | **48** | **41** | **7** | **2** |

Les 7 partielles portent 8 écarts (ASTK33 en porte deux). Aucune tâche « non-faite », « fausse » ni « régression ».

Points saillants des tâches jugées ok :

- **Les 30 P0/S1 tiennent sur `main`**, dont les deux S1 de la contre-visite du 09/10, désormais corrigés : comptage cyclique
  (ASTK39, snapshot à la saisie sur les deux chemins) et réservation après sortie partielle (ASTK121). Tiennent aussi les FK
  bornées à la société (ASTK1-6) et la suppression de produit en archivage (ASTK81).
- **Texte vieilli, code juste** (aucune tâche) : ASTK9, ASTK39 (préfixe « BLOCKED » resté dans la ligne), ASTK205, ASTK213
  (« faite » au lieu de la forme livrée). Les consommateurs ne lisent pas l'ancienne forme.
- **ASTK129** (garde « une vente = une sortie ») : la table AST des chemins a été rejouée, `oublies []`, `perimes []`. Elle ne
  joue que des chemins SEULS, d'où C-ASTK-VER-001 (§3).

## 2. Tests nommés

- **Exécutés.**
  - `check_fk_scoping` (lot 1) : garde OK, 508 points vérifiés.
  - Tests de la garde FK (lot 2, ASTK9) : `pytest`, 23 passed, garde OK.
  - Table AST de la garde ASTK129 (lot 7) : `oublies []`, `perimes []`.
- **Raisonnés, non rejoués localement.** Les autres tests nommés ont été lus contre leur commit et leur texte. Leur vert est
  celui du job `backend-tests` de la CI de `main` à `5ea32b58b` (vert, §0) ; aucune base de test locale n'a été construite
  (règle « Docker local test-DB : ne pas le combattre »).
- Les écarts de ce dossier ne viennent pas de tests rouges : ils portent sur des clauses que ces tests verts n'exercent pas,
  et sont prouvés par les sondes du §3.

## 3. Sondes (orchestrateur, conteneur jetable, transaction annulée)

Les sondes sont versionnées sous `docs/audits/sondes/ASTK/` (fonction `sonde(ctx)`, en-tête `SONDE` avec l'attendu).

| Sonde | Écart de | Verdict | Sortie |
|---|---|---|---|
| `C-ASTK-VER-001.py` | hors lot (lot 7) | **REPRO** | « livrer-partiel=200 sorties après livraison=4 après facture=14 après Installé=14 stock=16 (attendu 10 / 20) » |
| `C-ASTK-VER-002.py` | ASTK59 | **REPRO** | « quantite_appliquee=10 … statut_controle='normale' (facture 1200 HT, 10 x 100 entrés ; attendu exception) » |
| `C-ASTK-VER-003.py` | hors lot (lot 2) | **REPRO** | rôle Commercial sans `prix_achat_voir` : 200 `montant=['820.00']` sur `/stock/acomptes-fournisseur/`, 200 `[820.0]` sur `/ouverts/` |
| `C-ASTK-VER-004.py` | ASTK199 | **STATIQUE** | sonde HTTP écrite (stock 15 dont 10 rappelés, sortie scannée de 12, attendu 400) mais NON rejouée : le moteur Docker Desktop est tombé (500, VM WSL arrêtée) avant son exécution ; 1re version de la sonde (lecture du symbole) : `enregistrer_mouvement_scanne` contrôle la quarantaine : False |

Les sorties ci-dessus sont celles relevées par l'orchestrateur ; ce dossier les recopie sans les avoir rejouées.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Preuve | Fichier de plan |
|---|---|---|---|---|---|---|
| ASTK244 | C-ASTK-VER-001 | hors lot | **S1** | clause-manquante : garde par référence, 4 chemins sortent sous d'autres références | sonde VER-001 | `PLAN_AUDIT_FACTURATION.md` |
| ASTK245 | C-ASTK-VER-002 | ASTK59 | S2 | L6-jumeau : rapprochement 3 voies sur quantité saisie | sonde VER-002 | `PLAN_AUDIT_STOCK.md` |
| ASTK246 | C-ASTK-VER-003 | hors lot | S2 | règle de lecture divergente (acomptes + frère avoirs) | sonde VER-003 | `PLAN_AUDIT_STOCK.md` |
| ASTK247 | C-ASTK-VER-003 | ASTK14 | S2 (garde) | L5 : garde de classe aveugle à `montant` | lecture | `PLAN_AUDIT_STOCK.md` |
| ASTK248 | C-ASTK-VER-004 | ASTK199 | S3 | clause-manquante : quarantaine ignorée par scanner, mouvement manuel, expédition | sonde VER-004 | `PLAN_AUDIT_STOCK.md` |
| ASTK249 | C-ASTK-VER-004 | ASTK199 | S3 | même cause, consommation à « Installé » | sonde VER-004 + lecture | `PLAN_AUDIT_CHANTIERS.md` |
| ASTK250 | C-ASTK-VER-004 | ASTK199 | GATED | même cause, sortie de la facture : décision D-ASTK-VER-1 | lecture | `PLAN_AUDIT_FACTURATION.md` |
| ASTK251 | C-ASTK-VER-005 | ASTK33 | S3 | clause-manquante : cellule Stock offerte à un rôle refusé 403 | lecture + `test_non_admin_forbidden` | `PLAN_AUDIT_STOCK.md` |
| ASTK252 | C-ASTK-VER-006 | ASTK87, ASTK33, ASTK83 | S3 | L5 : tests affaiblis (mutants verts) | lecture | `PLAN_AUDIT_STOCK.md` |
| ASTK253 | C-ASTK-VER-007 | ASTK180, ASTK181 | S3 | clause-manquante : contrat « NOUVEAU » ≠ texte servi | lecture | `PLAN_AUDIT_STOCK.md` |

**Constats S1-S2 : 3** (C-ASTK-VER-001 à 003) ; C-ASTK-VER-004 tenu en S3 (sonde HTTP non rejouée, Docker hors service). Sans tâche : ASTK242 (L7, preuve en direct non jouée), voir §6.

**Routage.**
- **C-ASTK-VER-001 reste chez UN propriétaire (facturation).** Le correctif ne compose que des lectures existantes
  (`stock/selectors.py::mouvements_par_reference`, `installations/services.py::quantite_deja_sortie_chantier`) ; aucun
  fichier stock ni chantiers n'est modifié. Le test va dans le module facturation existant
  `apps/ventes/tests/test_facture_astk_sortie_unique.py`, pas dans la garde ASTK129 (fichier chantiers) : une tâche
  multi-propriétaires serait à scinder (METHODE §D.3.3), et TRANSVERSE n'accepte que les déplacements atomiques.
- **C-ASTK-VER-004 est découpé par propriétaire** : stock (ASTK248), chantiers (ASTK249), facturation (ASTK250, GATED).
  La facture suit la règle fondateur du 05/10 (« une facture n'est jamais bloquée par le compteur de stock ») : savoir si un
  rappel produit fait exception est une décision, D-ASTK-VER-1, à poser au fondateur et à graver dans
  `docs/audits/decisions.yml` (non ajoutée ici : ce fichier ne s'écrit qu'à partir d'une question posée).
- **ASTK246** ne touche aucun fichier d'ASTK241 (pas de `@after`) ; **ASTK247** porte `@after: ASTK243, ASTK246` et ne
  réécrit pas ASTK243.

## 4-bis. Critique Fable (1 appel, contexte frais, lecture seule)

Elle confirme les verdicts et les 8 écarts des lots, et ajoute :

- **Les frères de C-ASTK-VER-001.** La garde par référence rate quatre chemins, pas un : `livrer-partiel` (sous la référence
  du BC, BC resté CONFIRMÉ), l'ordre inverse facture puis `livrer-partiel`, la facture d'échéancier (`generer-facture`, même
  fonction), la livraison directe chantier et la consommation terrain F11. Le correctif attendu est UN sélecteur « déjà
  sorti pour cette vente » et une sortie au reliquat. La suite « Installé puis facture » a été ajoutée à la tâche par lecture
  (même mécanisme, non sondée ici).
- **Le frère de C-ASTK-VER-003** : les avoirs fournisseur (`avoir_fournisseur.py`) servent `montant_ht`, `montant_tva`,
  `montant_ttc`, `montant_impute`, `montant_disponible` avec la même règle `IsAnyRole`.
- **C-ASTK-VER-004 : relèvement en S2 proposé** (gardé en S3 ici, faute de sonde exécutée — METHODE §B.5 interdit un S2 STATIQUE ; à relever au rejeu de la sonde) : la quarantaine n'est respectée que par `sortir_lot_entrepot` ;
  `quantite_disponible_hors_quarantaine` n'a aucun appelant de production.
- **C-ASTK-VER-002** : elle proposait un `Coalesce(quantite_appliquee, quantite)`. La tâche réutilise plutôt
  `quantite_entree_ligne_reception` ligne par ligne, pour ne pas écrire une seconde fois la règle de repli.

## 5. Optionnel (hors correction ou spec, non déposé)

- **Autres lecteurs de la quantité saisie d'une réception** (sur-livraison plafonnée par ASTK59) : taille d'échantillon du
  contrôle qualité (`services_qualite_reception.py`, plan d'échantillonnage sur `ligne.quantite`) ;
  `services_catch_weight.py::quantite_valorisable_ligne` et `::ecart_pesee_ligne` (repli sur la quantité saisie). À juger un
  par un. La consommation du budget de département a aussi été citée par un vérificateur ; `consommation_budget` somme des
  engagements, pas des réceptions : non relu plus loin.
- **Garde de classe ASTK129** : elle ne joue que des chemins seuls. L'étendre aux suites composées (fichier chantiers) a du
  sens une fois ASTK244 sur `main` ; pas de `@after` entre deux plans, donc pas de tâche ici.
- **Lot 1** : `confirm_reception_fournisseur` verrouille un produit sans filtre société (lignes héritées) ; en-tête acheteur
  du PDF BCF.
- **Lot 4** : sonde de parité de la valorisation fournie (écran, à date, BI, T14 = 1 000 après découpe) ; elle tient.
- **Lot 5** : le test-du-test cité par ASTK59 est inexact (le mutant est tué par un autre test).
- **Lot 6** : d'autres écrans de création de fournisseur n'avertissent pas d'un nom en double ; la politique de facturation
  d'achat est lue sur le produit au moment de facturer.
- **Lot 8** : menus du poste scanner ouverts sur responsable/admin plutôt que sur `stock_modifier` ; `ecart_lots_non_affecte`
  sans appelant.

## 6. Couverture et non-couvert

- **Couvert.** 48 tâches sur 183 cochées (toutes les P0/S1, plus 25 % tirées). Commits et tests nommés lus ; 4 sondes jouées
  par l'orchestrateur ; une critique Fable.
- **Non couvert.**
  - Les 135 autres tâches cochées (hors échantillon).
  - **Preuves en direct (L7).** `check_acceptation.py --groupe ASTK` : 155 tâches à preuve exécutable, 0 couverte par un
    enregistrement, 154 dans la dette gelée `docs/audits/acceptation/ASTK/_dette.yml`. ASTK242 (cochée après le gel) n'y
    figure pas et son étape PA6.5 (Technicien responsable) n'a jamais été rejouée. Pas de nouvelle tâche : ASTK239 (ouverte)
    est l'acceptation UNIQUE du groupe ; son enregistrement devra couvrir ASTK242 et les écarts ASTK244-253 une fois livrés.
  - Le rouge du run planifié « Release verify (full suite) » à `5ea32b58b` n'a pas été examiné.
  - La sonde HTTP C-ASTK-VER-004 n'a pas été rejouée (Docker hors service) : à rejouer par le plan-run qui construit ASTK248, avant de relever la gravité.
- **Statut du registre.** Calculé `audité` après ce dépôt (`audit_registre.py status` : 183/198, 92 % — les 9 tâches
  constructibles ASTK244-249 et ASTK251-253 entrent au dénominateur, ASTK250 est GATED). Il ne passe pas `vérifié` : 4 constats
  S1-S2. Le groupe sort du cycle (METHODE
  §C.4.3) quand ASTK244-249 sont construites, D-ASTK-VER-1 tranchée, et qu'une contre-visite revient sans écart S1-S2.

## 7. Coût

- 8 vérificateurs opus (effort élevé) : environ 1,7 M de jetons au total.
- 1 critique Fable : environ 0,23 M de jetons.
- Orchestrateur : sondes, rédaction.

<!-- verifie pct: 96 ecarts_s1_s2: 3 -->
