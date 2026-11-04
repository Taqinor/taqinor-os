# Vérifie AANA — contre-visite de clôture du groupe analyse (X7), 04/11/2026

Commande `loop audit` (reprise du 04/11). La contre-visite du 01/11 avait déposé 15 écarts S1-S2 (AANA62-76) ; ils sont
cochés, la clôture est de nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod ;
la prod a été LUE (requêtes en lecture seule, accord permanent) par la seconde lentille du S1. Pile locale partagée ; chaque
sonde tourne en transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `d54c88db3`. Branche de claim : `verifie-aana-0411`.
- **Registre.** X7 `analyse`, groupe AANA, 78 tâches, 78 `[x]`.
- **Échantillon (graine = SHA `d54c88db3`).** Les 12 P0/S1 cochées + AANA62-73, 75, 76 (écarts du 01/11) + 13 tirées =
  **39 tâches**, 5 lots.
- **Déjà déposé, non redéposé.** ADEV107 (tableau Quote-to-Cash à la révision), ADOC191 (`lignes_vendues`), contre-visites
  ADEV, AMOT, ACHT du même jour.

## 1. Vérificateurs (5 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **34** | AANA2, 3, 4, 6, 8, 9, 12, 15, 19, 20, 21, 22, 26, 27, 30, 40, 43, 45, 52, 53, 56, 58, 62, 63, 65-70, 72, 75, 76, 78 |
| partiel | **5** | AANA23, 71, 73 (jumeau oublié), AANA64 (régression partielle d'outillage), AANA74 (acceptation cochée sur des rejeux partiels) |
| non-fait / faux | **0** | — |

Les écarts du 01/11 tiennent sur `main` (sondes VER-003 et VER4-010/011 rejouées : non reproduits). AANA2-4 (agent SQL) jugés
par lecture : l'agent ne s'exécute pas sur l'hôte. AANA68, AANA70 : preuve en direct dans la dette gelée du groupe.

## 2. Tests nommés

Tous présents dans un module existant. Tests faibles relevés : AANA67 (Kanban couvert par regex de source), AANA8 (calcul de
`allow_price` non exercé, service simulé), AANA72 (plancher de 90 tests alors que 96 existent). Aucun test rejoué en local
(CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AANA/C-AANA-VER4-010.py`, `-011.py` | AANA65, AANA62 | conformes |
| `docs/audits/sondes/AANA/C-AANA-VER4-020.py` | AANA73 | REPRO : facture importée « posted 2024-03-01 paid » créée émise, datée du jour, numérotée dans la série du mois |
| `docs/audits/sondes/AANA/C-AANA-VER4-021.py` | AANA71 | REPRO : tarif « 12.340 » et palier « 10:9.500 » refusés |
| `docs/audits/sondes/AANA/C-AANA-VER4-030.py` | AANA23 | REPRO : devis à deux options, commission 1 600 au lieu de 700 |
| `docs/audits/sondes/AANA/C-AANA-VER4-031.py` | critique | REPRO : devis à 3 villas, coût du job-costing 11 000 au lieu de 33 000 |
| `docs/audits/sondes/AANA/C-AANA-VER4-032.py` | critique | REPRO : la somme prescrite à l'agent SQL donne 50 000 pour un devis de 18 000 |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AANA-VER4-030 (+ -031) | AANA23 | S1 | la marge d'un devis somme les deux paniers et ignore le facteur multi-villas : job-costing et rentabilité faux (8 chantiers de prod, ex. marge −526 au lieu de +8 974) ; commission MARGE_INTERNE fausse (sans plan en prod aujourd'hui) | REPRO (+ L2, prod lue) | AANA80 (après ADOC191) |
| C-AANA-VER4-032 | critique | S2 | le prompt de l'agent SQL prescrit la somme des lignes : un devis à deux options additionne ses paniers | REPRO | AANA81 |
| C-AANA-VER4-020 | AANA73 | S2 | colonnes d'import mappées mais jamais lues (date, statut de paiement) ; D-AANA-VER4-1 = les retirer | REPRO (+ L2) | AANA82 |
| C-AANA-VER4-021 | AANA71 | S3 | tarif exact au centime refusé (« 12.340 ») | REPRO | AANA83 |
| critique | AANA71 | S3 | date de validité illisible écartée en silence (tarif) ; date de pose illisible écartée en silence (équipements) | lecture | AANA84, AANA85 |
| C-AANA-VER4-012 | AANA64 | S3 | caractères de contrôle dans `pile_locale.ps1` (corrigés depuis) ; aucune garde ne les voit | rejeu PowerShell 5.1 | AANA86 |
| critique | AANA58 | S3 | taux d'acceptation : une V1 acceptée puis révisée sort des acceptés et des envoyés | lecture | AANA87 |
| critique | AANA19 | S3 | panneau de visite : lignes des deux paniers à côté du total de l'option retenue | lecture | AANA88 |
| critique | — | S4 | `devis_pour_projet` (app parquée) somme les deux paniers | lecture | AANA89 |
| C-AANA-VER4-040 | AANA74 | S3 | acceptation en direct incomplète (gestes d'AANA65, 68, 70, 71, 75, 76 jamais rejoués) | — | AANA90 (`@acceptation`) |

Seconde lentille sur le S1 : maintenu, élargi (la commission n'a pas de plan en prod ; le S1 vivant est le job-costing et la
rentabilité). Seconde lentille sur -020 : réduit à S2 (montant 0, aucune relance ; API seule). Critique Fable (1) : facteur
multi-villas, agent SQL, taux d'acceptation, dates illisibles, panneau de visite.

## 5. Optionnel (non déposé)

- AANA66 : la recalibration des probabilités n'est atteignable que par l'app parquée `mlops` (aucun chiffre faux).
- AANA19 : `reporting/calepinage_kpis.py::indicateurs_calepinage` compte `statut == accepte` (effet non prouvé).
- AANA20 : une facture « payée » avec reliquat compte en attente mais pas dans les créances.
- AANA6 : commentaires « retombe sur DATABASE_URL » périmés ; AANA15 : cible archivée épinglable en favori.

## 6. Couverture et sortie de cycle

- **Couvert.** 39 tâches sur 78 cochées ; 7 sondes jouées (et 3 rejouées) dans la pile locale ; prod lue pour le S1.
- **Non couvert.** Les 39 autres tâches cochées ; aucun rejeu navigateur ; agent SQL non exécuté (prompt seul).
- **Statut.** 1 écart S1 et 2 S2 ⇒ AANA reste dans le cycle : prochaine clôture due quand AANA80-90 seront cochées.

## 7. Coût

- 5 vérificateurs + 2 secondes lentilles + 1 lot de sondes de critique (opus, effort élevé) ≈ 1,6 M de jetons ; 1 critique
  Fable ≈ 0,2 M ; 1 rédacteur.

<!-- verifie | groupe: AANA | pct: 100 | ecarts_s1_s2: 3 -->
