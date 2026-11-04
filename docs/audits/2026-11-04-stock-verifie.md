# Vérifie ASTK — 4ᵉ contre-visite de clôture du groupe stock (J3), 04/11/2026

Commande `loop audit` (reprise du 04/11). Le groupe avait 2 écarts S1-S2 à la clôture du 01/11 (ASTK255-256) ; ces deux
tâches sont cochées, la clôture est donc de nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a
rien écrit en prod. Pile locale : migrations manquantes appliquées en cours de route (une sonde rejouée après coup).

## 0. Préconditions

- **SHA.** `origin/main` = `c38868a62`. Branche de claim : `verifie-astk-0411`.
- **Registre.** J3 `stock`, groupe ASTK, 202 tâches, 201 `[x]` (ASTK250 ouverte).
- **Échantillon (graine = SHA `c38868a62`, plafond 48).** Les 34 P0/S1 cochées + ASTK255-256 (écarts du 01/11) + 12 tirées
  = **48 tâches**, 6 lots de 8.
- **Déjà déposé, non redéposé.** Audits de parcours PA1/PA3/PA4 (ACVI, ADVS, AARG) ; ASTK239 (preuve en direct) reste
  dans la dette d'acceptation gelée du groupe.

## 1. Vérificateurs (6 lots de 8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **44** | ASTK1-9, 11, 13, 19, 28, 32, 33, 37-43, 46, 55-60, 81, 83, 86-88, 90, 98, 108, 109, 120, 129, 135, 140, 255, 256 |
| partiel | **4** | ASTK31 (jumeau oublié), ASTK82 (société lue sur l'acteur), ASTK239 (preuve en direct, déjà connue), ASTK244 (jumeau oublié) |
| non-fait / faux / régression | **0** | — |

ASTK255-256, écarts du 01/11 : fermés (sondes et enregistrements PA6.2/PA6.3 PASS). Textes vieillis sans défaut : ASTK1
(409 ENF11), ASTK38 (règle ASTK37/39 postérieure), ASTK39 (préfixe « partiel » périmé).

## 2. Tests nommés

Tous présents dans un module existant ; aucun affaibli (comparaisons « id étranger = id absent » conservées après ENF11).
Garde ASTK129 rejouée sur l'hôte : 17 sites, `oublies []`, `perimes []`. Aucun test Django rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ASTK/C-ASTK-VER4-001.py` | ASTK1-8 | conforme (société bornée sur 8 surfaces) |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-010.py`, `C-ASTK-VER4-011.py` | ASTK38-41 | conformes (écart d'inventaire, valorisation à date, BI) |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-020.py` | ASTK56-60 | conforme (réception, annulation, GR/IR) |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-030.py` | ASTK98, 120, 135 | conforme (une seule sortie sur trois chemins) |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-021.py` | ASTK82 | REPRO |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-050.py` | ASTK31 | REPRO |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-040.py`, `C-ASTK-VER4-041.py` | ASTK244 | REPRO |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-040-L2.py` | ASTK244 (seconde lentille) | REPRO, élargi aux acomptes |
| `docs/audits/sondes/ASTK/C-ASTK-VER4-060.py` | critique (annulation) | REPRO partiel |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASTK-VER4-040 | ASTK244 | S1 | une facture émise (acompte 30 % compris) sort tout le panier ; F11 puis la livraison directe chantier le ressortent : 20 sorties pour une vente de 10 | REPRO (+ L2) | ASTK257, ASTK258 |
| C-ASTK-VER4-041 | ASTK244 | S1 | livraison directe chantier après facture : entrée puis sortie sans lire le déjà-sorti, invisible pour la lecture partagée | REPRO | ASTK259 |
| C-ASTK-VER4-060 | critique | S2 | facture d'acompte annulée : le matériel reste sorti, sortie de « Signé » refusée (409) ; D-ASTK-VER4-1 = retour à l'annulation | REPRO | ASTK262, ASTK263 |
| C-ASTK-VER4-021 | ASTK82 | S3 | superutilisateur sans société : suppression d'une catégorie peuplée (produits décatégorisés) | REPRO | ASTK260 |
| C-ASTK-VER4-050 | ASTK31 | S3 | palette scellée modifiable par ses enfants (API seule) | REPRO | ASTK261 |

Seconde lentille sur le S1 : maintenu, élargi (le crochet d'émission sort tout le panier dès la première tranche émise, quel que
soit son type). Critique Fable (1) : trois défauts du plan corrigés avant dépôt (formule F11 cumulée sur plusieurs
interventions, sortie directe sous la référence du chantier, lecture partagée dans les deux sens) et le S2 d'annulation.

## 5. Optionnel (non déposé)

- `stock/services.py::confirm_reception_fournisseur` verrouille le produit sans filtre société (données héritées seulement).
- `services_wms.py` cross-dock lit `ligne.quantite` et non `quantite_appliquee` (sans écran).
- `facturer_bcf_sur_commande` sans verrou (double clic théorique).
- Lignes de comptage tournant pré-remplies au stock de génération (cas limite non sondé).

## 6. Couverture et sortie de cycle

- **Couvert.** 48 tâches sur 201 cochées ; 11 sondes jouées dans la pile locale.
- **Non couvert.** Les 153 autres tâches cochées ; aucun rejeu navigateur.
- **Statut.** 2 écarts S1 et 1 S2 ⇒ ASTK reste dans le cycle : prochaine clôture due quand ASTK257-263 seront cochées.

## 7. Coût

- 6 vérificateurs + 1 seconde lentille + 1 sonde de critique (opus, effort élevé) ≈ 1,6 M de jetons ; 1 critique Fable
  ≈ 0,15 M ; 2 rédacteurs.

<!-- verifie | groupe: ASTK | pct: 99 | ecarts_s1_s2: 3 -->
