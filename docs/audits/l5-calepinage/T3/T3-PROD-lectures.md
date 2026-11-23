# T3-PROD — toutes les lectures de la production annuelle d'un même calepinage (23/11/2026)

Calepinage **2040** « T3-PROD Villa Casablanca 4x710 » (compte `rev_b2`, bureau 1440 × 900 clair) : 4 × Canadien
Solar 710 W (2,84 kWc), Casablanca, 30° sud, onduleur Huawei 5 kW repris du devis, voiture ajoutée, devis
**DEV-202611-0018** généré avant la simulation ; société en météo pluriannuelle 2014-2023 ; simulé à 11:19.
Valeur de référence servie : `GET …/2040/resultat/` → `production.total.p50_kwh` = **5 905,7 kWh** (borne haute,
17 pertes non renseignées). Lectures relevées entre 11:20 et 12:00, avant le passage à 30 panneaux (ACAL1702).

Captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T3/T3-PROD/cap/`.

| # | Où | Libellé exact | Valeur | Écart au P50 servi | Capture / source |
|---|----|---------------|--------|--------------------|------------------|
| 1 | Liste des calepinages | « 2,84 kWc · 4 panneaux · 5 906 kWh/an » | 5 906 | 0 | `L1-liste.png` |
| 2 | Étape Panneaux (Guidé), carte du haut | « Production · estimation de la pose — 4 542 kWh / an » (et « De la consommation ≈ 66 % ») | 4 542 | **−23,1 %**, sans mention | `L2-panneaux-guide.png` |
| 3 | Bandeau du projet | « 4 panneaux · 2,84 kWc · 1 onduleur 5 kW » (ou « Lead · facture 900 MAD / mois » selon l'étape) | aucune production | — | `B4-devis-annonce.png`, `L2-panneaux-guide.png` |
| 4 | Étape Résultats (Guidé) | « Production la première année · au plus — Plafond 5 906 kWh » | 5 906 | 0 | `L3d-resultats-guide.png` |
| 5 | Atelier Expert, colonne droite | « Estimation rapide de l'atelier — avant la simulation — Simulation : P50 5 906 kWh/an (borne haute — 17 pertes non renseignées) » | 5 906 | 0 | `B4-devis-annonce.png` |
| 6 | Atelier Expert, colonne droite | « Le devis annonce : 4 542 kWh/an — production standard de la ville (étude technique : +30,0 % — borne haute — 17 pertes non renseignées) » | 4 542 | −23,1 %, **écart nommé** | `B4-devis-annonce.png` |
| 7 | Atelier Expert, résumé sous la vue | « 4 panneaux · 2,84 kWc · P50 5 906 kWh/an (simulation) » | 5 906 | 0 | texte `B5-Production.txt` |
| 8 | Onglet Production | « PRODUCTION ANNUELLE (P50) 5 906 kWh — borne haute — 17 pertes non renseignées » ; « PRODUCTIBLE 2 079,5 kWh/kWc » ; « DE LA CONSOMMATION 29 % » | 5 906 | 0 | `B6-Production.png` |
| 9 | Onglet Économie | « Production année 1 — 4 542 kWh — devis DEV-202611-0018 — production annuelle (moteur de devis) » | 4 542 | **−23,1 %**, source nommée mais aucune phrase d'écart (ACAL1611 non fait) | `B7-conomie.png` |
| 10 | Rapport d'étude PDF (p3 Synthèse, p12 Production) | « Production annuelle P50 5 905,7 kWh — borne haute — 17 pertes non renseignées » | 5 905,7 | 0 | `rapB.pdf` |
| 11 | Présentation compacte PDF (p2) | « Production : celle du devis DEV-202611-0018 (4542 kWh/an) » | 4 542 | −23,1 %, source nommée | `compacteB.pdf` |
| 12 | PDF client `/proposal` (p1, p2) | « 4 542 kWh/an — Production estimée » ; « 4 542 kWh / an produits » | 4 542 | −23,1 % (document du devis, règle #4) | `proposalB.pdf` |
| 13 | Vue « Montrer au client » | « 4 panneaux » seulement | aucune production | — | `L5-montrer-client.png` |
| 14 | Fiche « Pertes expliquées en 5 postes » PDF | parts en %, « La production annoncée au client reste celle de son document commercial » | aucune production | — | `postesB-p1.png` |

## Ce qui diffère encore

- **Deux valeurs circulent : 5 906 (simulation) et 4 542 (devis / « production standard de la ville »), écart
  −23,1 % (ou +30,0 % vu du devis).** Sur 11 lectures chiffrées, 5 portent 4 542 (n° 2, 6, 9, 11, 12) et 6 portent
  5 906 (n° 1, 4, 5, 7, 8, 10).
- **Deux lectures diffèrent SANS explication à l'écran** : la carte de l'étape Panneaux (n° 2), qui appelle
  « estimation de la pose » le chiffre du devis, et l'onglet Économie (n° 9), qui ne dit pas l'écart au P50
  (ACAL1611). Les trois autres (n° 6, 11, 12) nomment leur source.
- La part de la consommation diffère aussi : « ≈ 66 % » (carte Panneaux) contre « 29 % » (onglet Production) et
  « Couverture des besoins 28,81 % » (rapport p3).

## Jumeau sur le calepinage 2039 (13 modules dont 4 non raccordés, P50 servi 10 224,3 kWh sur 6,39 kWc)

- Étape Panneaux : « Production · estimation de la pose 14 620 kWh / an » et « ≈ 174 % » de la consommation —
  **+43,0 %** au-dessus du P50, chiffre qui compte encore les 4 panneaux raccordés à rien (`L6-A-panneaux.png`).
- Bandeau « 13 panneaux · 9,23 kWc · 1 onduleur 5 kW », Résultats « 10 224 kWh » + « Panneaux 13 » +
  « Puissance 6,39 kWc », rapport p3 « Puissance crête 9,23 kWc » + « P50 10 224,3 kWh » + « Productible
  1 600,0 kWh/kWc » (= 10 224 / 6,39) : rien ne dit que 4 panneaux ne sont pas comptés (ACAL1602 partiel).
