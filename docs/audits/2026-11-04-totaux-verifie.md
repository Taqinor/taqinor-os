# Vérifie ATOT — contre-visite de clôture de la lentille totaux (X2), 04/11/2026

Commande `loop audit` (reprise du 04/11). Les écarts du 01/11 (ATOT46-52) sont cochés : 50 tâches sur 50, la clôture est de
nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod. Pile locale partagée ;
chaque sonde tourne en transaction annulée ; une sonde d'écran a été rejouée sous node sur une copie d'`origin/main`.

## 0. Préconditions

- **SHA.** `origin/main` = `64c9c7317`. Branche de claim : `verifie-atot-0411`.
- **Registre.** X2 `totaux`, groupe ATOT, 50 tâches, 50 `[x]`.
- **Échantillon (graine = SHA `64c9c7317`).** Les 18 P0/S1 cochées + ATOT46-50, 52 (écarts du 01/11 ; 51 tirée) + 8 tirées
  = **32 tâches**, 4 lots de 8.
- **Déjà déposé, non redéposé.** AGNR63-66 (échéancier négatif quand le TTC baisse), AGNR71 (aperçu multi-propriétés),
  ASEC67-68 (émission et avoir sans `encaisser`), AMOT118 (niveau de règles 12).

## 1. Vérificateurs (4 lots de 8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **28** | ATOT2, 3, 5, 6, 10, 11, 12, 17, 18, 22, 25, 26, 31, 32, 35, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 51, 52 |
| partiel | **2** | ATOT15 (test affaibli), ATOT43 (créditable lu en TTC seulement) |
| régression | **1** | ATOT24 (aperçu « N propriétés » sans les produits liés, depuis AGNR36) |
| faux | **1** | ATOT50 (l'invariant de la machine de facturation ne peut plus échouer) |

Écarts du 01/11 : ATOT46-49, 52 fermés (sonde VER-006 rejouée : grand livre équilibré) ; ATOT50 faux. ATOT31 et ATOT38
remplacés par VNT75 (changement voulu). ATOT44 tient (sonde VER4-020 saine), preuve en direct en dette d'acceptation.

## 2. Tests nommés

Tous présents dans un module existant. Tests faibles relevés : la machine `test_atot_machine_facturation.py` (ATOT15/50),
`solar.atot.test.mjs` (rail construit sans produits). Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ATOT/C-ATOT-VER4-001.py` | ATOT15 | REPRO : devis 150 000 sur-facturé à 240 000, l'invariant ne lève pas |
| `docs/audits/sondes/ATOT/C-ATOT-VER4-002.py` | ATOT2 | STATIQUE : aucune prise de verrou de vente avant la borne d'émission |
| `docs/audits/sondes/ATOT/C-ATOT-VER4-010.py` | ATOT43 | REPRO : avoir 10 000 HT à 10 % sur une tranche dont la base à 10 % est 8 000 |
| `docs/audits/sondes/ATOT/C-ATOT-VER4-020.py` | ATOT44 | conforme |
| `docs/audits/sondes/ATOT/C-ATOT-VER4-021.py` | ATOT50 | REPRO : devis 1 200 facturé deux fois en entier, invariant vert |
| `docs/audits/sondes/ATOT/C-ATOT-VER4-030.mjs` | ATOT24 | REPRO : aperçu « 3 × 53 800 » contre un rail à 18 800 (écart déjà déposé AGNR71) |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ATOT-VER4-010 | ATOT43 | S2 | avoir de révision sur une vente multi-taux ventilé au prorata de l'écart sans borner par la base par taux de la facture visée : base et TVA négatives à un taux sur ce document | REPRO | ATOT56 |
| C-ATOT-VER4-001 (+ -021) | ATOT15, ATOT50 | S3 | l'invariant « Σ factures ≤ devis » de la machine de facturation lit `plan_facturation` et ne peut plus échouer | REPRO | ATOT57 |
| C-ATOT-VER4-002 | ATOT2 | S3 (S1 si la course se reproduit) | émission sans verrou de vente : deux brouillons émis en même temps factureraient deux fois | STATIQUE | ATOT58 |
| C-ATOT-VER4-022 | ATOT44 | S3 | l'avoir « à confirmer » d'une révision acceptée normalement n'a ni écran ni route | lecture | ATOT59-62 |

Aucun S1 prouvé : ni seconde lentille ni critique Fable (METHODE §C.4). ATOT58 commence par le test rouge à deux fils ; s'il
reproduit la double émission, la gravité est relevée à S1 au DONE LOG.

## 5. Optionnel (non déposé)

- `FactureLicenceMarquerPayeeView` sans verrou de ligne (double « marquer payée » théorique).
- `BonCommandeAdmin` laisse `statut` modifiable.
- La docstring de la machine de facturation dit encore que la révision ignore les consolidées.

## 6. Couverture et sortie de cycle

- **Couvert.** 32 tâches sur 50 cochées ; 6 sondes jouées (et VER-006 rejouée).
- **Non couvert.** Les 18 autres tâches cochées ; aucun rejeu navigateur ; course d'émission non jouée.
- **Statut.** 1 écart S2 ⇒ ATOT reste dans le cycle : prochaine clôture due quand ATOT56-62 seront cochées.

## 7. Coût

- 4 vérificateurs (opus, effort élevé) ≈ 0,9 M de jetons ; 1 rédacteur ; aucun appel Fable (aucun S1 prouvé).

<!-- verifie | groupe: ATOT | pct: 100 | ecarts_s1_s2: 1 -->
