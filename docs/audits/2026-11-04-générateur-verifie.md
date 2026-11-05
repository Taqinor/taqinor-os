# Vérifie AGNR — contre-visite de clôture du groupe générateur (D4), 04/11/2026

Commande `loop audit` (reprise du 04/11). Les écarts du 01/11 (AGNR55-60) sont cochés : 62 tâches sur 62, la clôture est de
nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod ; la prod a été LUE
(requête en lecture seule, accord permanent) pour mesurer la fréquence d'un écart. Pile locale partagée ; chaque sonde tourne
en transaction annulée ; les fonctions pures de l'écran ont été rejouées sous node depuis le dépôt principal.

## 0. Préconditions

- **SHA.** `origin/main` = `4cd568403`. Branche de claim : `verifie-agnr-0411`.
- **Registre.** D4 `générateur`, groupe AGNR, 62 tâches, 62 `[x]`.
- **Échantillon (graine = SHA `4cd568403`).** Les 16 P0/S1 cochées + AGNR55-58, 60 (écarts du 01/11 ; 59 tirée) + 11 tirées
  = **32 tâches**, 4 lots de 8.
- **Déjà déposé, non redéposé.** AMOT125 (écran sans niveau de règles), AMOT118 (niveau de règles 12), ADEV106-111, AANA80-90.

## 1. Vérificateurs (4 lots de 8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **24** | AGNR1, 5, 6, 8, 10, 11, 13, 14, 15, 16, 26, 27, 31, 37, 49, 50, 51, 53, 54, 55, 56, 57, 59, 60 |
| partiel | **7** | AGNR4 (fichier mémoire jamais créé), AGNR18, 34, 36, 52 (jumeau oublié), AGNR42 (preuve en direct), AGNR58 (avertissement dans le même clic) |
| faux | **1** | AGNR41 (garde construite sur une structure déjà déplacée : elle ne voit plus sa propre classe) |

Écarts du 01/11 : AGNR55-60 fermés (sondes VER-004, VER-005 rejouées ; C-AGNR-VER-007 ne se reproduit plus).

## 2. Tests nommés

Tous présents dans un module existant. Tests faibles relevés : AGNR58 (lecture de source seule), AGNR16 (deux cas absents),
AGNR27 (extrait de catalogue). Aucun test rejoué en local (CI d'abord) ; `solar.agnrKwcLignes.test.mjs` rejoué : 7/7.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AGNR/C-AGNR-VER4-001.py` | AGNR6 | conforme : factures hiver/été lues pareil par l'étude, le profil horaire et la page publique |
| `docs/audits/sondes/AGNR/C-AGNR-VER4-010.py` | AGNR50, 52 | REPRO : remise ⇒ TTC 17 000 → 8 500, dernière tranche −2 900,20 MAD imprimée |
| `docs/audits/sondes/AGNR/C-AGNR-VER4-011.mjs` | AGNR34 | REPRO : mois corrigé à l'écran absent du corps enregistré (aperçu 5 979 kWh) |
| `docs/audits/sondes/AGNR/C-AGNR-VER4-012.py` | critique | REPRO : prix négocié sur une vente acceptée et suppression d'une ligne ⇒ tranche négative ; agricole et résidentiel : tranche coupée en silence |
| `docs/audits/sondes/AGNR/C-AGNR-VER4-030.py` | AGNR18 | REPRO : 10 × 550 W + 10 × 710 W ⇒ 11,0 kWc au serveur, 12,6 à l'écran ; prod : 0 devis mixte sur 469 |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AGNR-VER4-010 (+ -012) | AGNR50, AGNR52 | S1 | échéancier mixte jamais recalé quand le TTC baisse sans le renvoyer : dernière tranche négative imprimée sur les devis C&I, devis envoyés compris ; prix négocié et suppression de ligne aussi | REPRO (+ L2) | AGNR63, AGNR64 (DEVIS), AGNR65 (FACTURATION), AGNR66 (MOTEUR) |
| C-AGNR-VER4-011 | AGNR34 | S2 | mois corrigé dans une grille dérivée de l'hiver/été perdu sans avertissement à l'enregistrement | REPRO (node) | AGNR67, AGNR68 |
| C-AGNR-VER4-030 | AGNR18 | S3 | kWc serveur au watt de la première ligne de panneaux (latent : aucun devis mixte en prod) | REPRO (+ prod lue) | AGNR69, AGNR70 |
| C-AGNR-VER4-031 | AGNR36 | S3 | aperçu « N propriétés » classé sur la désignation seule | REPRO (node) | AGNR71 |
| C-AGNR-VER4-032 | AGNR41 | S3 | garde des champs d'écran sans consommateur aveugle aux hooks | lecture (probe) | AGNR72 |
| C-AGNR-VER4-020 | AGNR58 | S3 | avertissement « ligne sans produit » affiché dans le même clic que l'enregistrement | lecture | AGNR73 |
| C-AGNR-VER4-040 | critique | S3 | prix/kWc de l'écran divisé par le kWc de l'option « sans » | lecture | AGNR74 |
| C-AGNR-VER4-021 | AGNR59 | S4 | restriction du fondateur du 01/11 absente de `decisions.yml` | lecture | AGNR75 |

Tout changement de chiffre imprimé passe par le niveau de règles 12 (AMOT118) : nouveaux rendus seulement. Seconde lentille
sur le S1 : maintenu (C&I), élargi (correction sur place d'un devis envoyé, remplacement des lignes) ; résidentiel borné case
par case. Critique Fable (1) : dix chemins d'écriture sans la règle, prix négocié, divergences écran / corps, prix/kWc.

## 5. Optionnel (non déposé)

- AGNR4 : le fichier mémoire des décisions AGNR n'est pas recréé (AGNR46 l'a fondu dans `decisions-audit-0810.md`).
- Brouillon local ancien sans provenance des mois : marque 12 mois tapés (s'éteint avec le temps).
- `ListesPrixPage.jsx` : prix fixés sans mention HT ; `_pct_txt` imprime un point décimal en français.
- `onProduitChange` ne réinitialise pas `prixRelu`.

## 6. Couverture et sortie de cycle

- **Couvert.** 32 tâches sur 62 cochées ; 6 sondes jouées (et 3 rejouées) ; prod lue pour le kWc mixte.
- **Non couvert.** Les 30 autres tâches cochées ; aucun rejeu navigateur ; rendu PDF C&I de la V2 négociée inféré.
- **Statut.** 1 écart S1 et 1 S2 ⇒ AGNR reste dans le cycle : prochaine clôture due quand AGNR63-75 seront cochées.

## 7. Coût

- 4 vérificateurs + 1 seconde lentille + 1 lot de sondes de critique (opus, effort élevé) ≈ 1,4 M de jetons ; 1 critique
  Fable ≈ 0,2 M ; 1 rédacteur.

<!-- verifie | groupe: AGNR | pct: 100 | ecarts_s1_s2: 2 -->
