# Lot B — pose des panneaux et électrique (tour 2 du L5, consolidation du 23/11/2026)

Relecteurs lus : F2-POSE-a, F2-POSE-b, F2-ELEC-a, F2-ELEC-b (verdicts, constats, rapports, captures S1-S2 regardées : réouverture
60 → 5, champ au sol, pan étroit, schéma électrique, « Régler », toit « 4 pans », PDF du schéma). Code lu sur la tête `ba8ca4707`
(branche, avec les 74 commits pliés depuis `bfb859c90`) : chaque cause dite « lue » a été ouverte dans ce dossier ; une cause « probable » commence sa tâche par « reproduire puis corriger ».

## 1. Comptes
- Verdicts lus : 71 lignes, 70 corrections (ACAL827 a deux lignes, la seconde complète la première) : **ok 41 · partiel 28 · non-fait 1
  (ACAL547) · faux 0 · régression 0 · déjà-présent 0** ; non essayés (jamais comptés) : voir § 6.
- Constats vus 46 (S1 1, S2 9, S3 32, S4 4) : **retenus 44** (S1 1, S2 9, S3 31, S4 3), doublon 1 (POSE-b-004 = POSE-a-011),
  écarté-faux 1 (ELEC-a-012). Artefacts d'instrument : 0 constat (CALX109 et les lenteurs avant 05 h 45 UTC n'apparaissent dans aucun constat du lot).
- Tâches écrites : **55**, ACAL1500-ACAL1554 (M0 1, M1 11, M2 40, GATED 2, acceptation 1) ; 29 reprises (une par `partiel` ou `non-fait`,
  regroupées quand la cause est la même : ACAL1505 pour 546+547, ACAL1519 pour 4 constats de grille, ACAL1532 pour 1296+1298+POSE-b-011).
- Modèles : opus 9 (production, pavage, `core`, ratio, S1 gated), haiku 3, sonnet 43 ; événements : `registre/evenements/T2-consolidation-B.jsonl` (46).

## 2. Classes
Neuve : **K-COLONNE-ETROITE** (`T2/classes/K-COLONNE-ETROITE.md` : grilles à point de rupture de fenêtre, 10 endroits listés dont 9 violés).
Complétées (`T2/classes/complement-B.md`) : K-GRANDEUR-UNIQUE (6 endroits), K-RETOUR-FAUX (7), K-SAISIE-PERDUE (2), K-IMPASSE (3),
K-JARGON, K-ACTION-ENFOUIE, K-STYLE (jeton désactivé).

## 3. Choix de produit tranchés (aucune question à Reda ; jamais enregistrés comme décisions de Reda)
| # | Choix | Retenu (règle appliquée) | Coût si faux |
|---|---|---|---|
| 1 | cible des « Régler » électriques | l'onglet existant qui porte le point (Verdict, Cheminement, Décisions) — le plus simple, aucun écran neuf (ACAL1506) | un onglet expert au lieu d'un champ dans l'étape ; réversible (une table de cibles) |
| 2 | un seul compte de points | la ligne de contrôle ; le dossier dit « À compléter » sans nombre (ACAL1539) | le détail des motifs reste un clic plus loin |
| 3 | PDF « du schéma » | rendre le schéma dessiné (maquette `Schema.dc.html`), pas renommer le bouton (ACAL1507-1508) | une route et un rendu de plus à tenir |
| 4 | alerte d'ombre sans seuil réglé | dire la perte calculée du facteur d'ombrage, jamais un seuil inventé (ACAL1532) | une phrase de plus quand l'ombre est faible |
| 5 | carte « Couvrir la facture » | borner à ce qui tient, dire « sur N nécessaires » (ACAL1502) | une recommandation plus modeste |
| 6 | auto-raccordement 1 × 20 sur 2 entrées (ELEC-a-012) | ÉCARTÉ : règle fondateur du 24/08/2026 lue dans `core/electrique/chaines.py::_choisir_longueur` | aucun (règle écrite) |
| 7 | contrôle rapide de chaîne | température chaude facultative, repli 70 °C sourcé (D-ENF-SEUILS-DEFAUT du 30/10/2026) (ACAL1545) | aucun nouveau chiffre inventé |
| 8 | panneaux colorés par ensoleillement | oui (maquette Panneaux v2, OpenSolar) (ACAL1515) | un matériau par module de plus dans la scène |
## 4. Décisions ouvertes à écrire dans `docs/audits/decisions.yml` (listées, non écrites)
1. **Température de froid de dimensionnement des chaînes** (tâche GATED ACAL1553). Lu dans le code : `froid_c` = minimum de l'année TYPE du TMY
   (4,18 °C à Casablanca, −2,8 °C à Fès), plancher −5 °C seulement si la météo manque ; la règle « TMY avant le plancher » n'est écrite nulle part
   de sourcé et un TMY lisse les extrêmes (Voc à froid plus bas, plus de modules par chaîne). Options : (a) minimum du TMY (actuel) ; (b) le plus bas
   du TMY et de −5 °C ; (c) −5 °C toujours. Recommandation : (b). Coût si faux : tension de chaîne mal bornée par grand froid (matériel).
2. **D-ACAL-75** (déjà ouverte, rejouer ou re-poser) : la tâche GATED ACAL1552 y renvoie pour le cas S1 « Remplir automatiquement » (60 → 5).
   Aucun numéro neuf n'est pris ici.
## 5. Tâches → fichiers (disjonction : les tâches d'un même cluster partagent au moins un fichier et suivent `@after`)
- Cluster A (atelier carte, 14) : 1503 1510 1515 1516 1519 1520 1521 1522 1524 1527 1528 1529 1530 1552 — `scene3d.ts`, `layoutEditor.ts`, `roof-tool-pro11.ts`, `roofbuilder.css`, `zones.test.ts`.
- Cluster B (électrique serveur, 6) : 1506 1512 1538 1539 1540 1553 — `services/pret_a_envoyer.py`, `services/electrique.py`, `views/raccordement.py`.
- Cluster C (étape Panneaux, 5) : 1501 1502 1514 1517 1532 — `EtapePanneaux.jsx`, `shadingUi.ts`, `panneaux/constructeur.js`.
- Cluster D (balayage, 5) : 1504 1505 1525 1526 1533 — `optimizer.ts`, `matrix.ts`, `orientationOmbre.ts`, `roofSetbackEdge.ts`.
- Cluster E (affectation, 4) : 1509 1535 1536 1541 — `plan/AffectationChaines.jsx`, `plan/ImportAffectation.jsx`.
- Cluster F (schéma, 2) : 1507 1551 ; puis 1508 (front, `@after` 1507) — `views/schema.py`, `services/sld.py`, `EtapeSchema.jsx`.
- Seules : 1500 (contrat), 1511 (`ModeTerrain.jsx`), 1513 (`panStats.ts`), 1518 + 1531 (`Fixation.jsx`, `controles_pose.py`), 1523 (`chassisPavage.ts`),
  1534 (`PanneauDocuments.jsx`), 1537 (`core/electrique/chaines.py`), 1542 (`services/chaines.py`), 1543 (`GroupesPretAEnvoyer.jsx`), 1544 (`VerdictElectrique.jsx`),
  1545 + 1546 (`views/electrique.py`, `ControleChaine.jsx`), 1547 (`ParcoursDuPan.jsx`), 1548 (`DossiersReglementaires.jsx`), 1549 (`SaisiesElectriques.helpers.js`), 1550 (`DecisionsElectriques.jsx`).
- Interfaces : 1500 → 1517 (clé `refus`, contrat d'abord) ; 1507 → 1508 → 1551 ; 1545 → 1546. À vérifier à l'assemblage : fichiers communs avec les lots A (toit : `roof-tool-pro11.ts`, `zones.ts`) et E (écrans, `roofbuilder.css`).
## 6. Preuves à rejouer au tour 3 (pas des défauts vus)
ACAL577 et ACAL582 (compte du SERVEUR d'un pan à coupure ou à châssis : aucun écran ne l'affiche) ; ACAL593 « recentrer sur le lead » (fond de carte indisponible) ;
ACAL568 avec un devis lié ; ACAL566 système « bac acier » seul ; ACAL551 silhouette ambre ; ACAL553 collage réussi dans un AUTRE pan ; zone Coin du plan de lestage
(définition par réglage société, rien de faux lu) ; ACAL895 (commande serveur interdite sur la pile) ; ACAL664 à 50 °C ; refus non rejoués d'ACAL830, ACAL782, ACAL783, ACAL642 ;
ACAL1188 (aucun micro-onduleur au catalogue de démonstration) ; ACAL627 « fiche incomplète » ; côté réseau du schéma après simulation ; WebKit, thème sombre, tablette non joués ;
vu une fois, non reproduit : glisser près d'un coin qui déforme le toit (16 → 21 panneaux, POSE-a), « vider » les champs du châssis, carte « 14,40 kWc » (720 W) contre 14,20, « 10 kW » sous « Deye 15 kW » après un premier Appliquer.
Les calepinages 2003 et 2008 ont un document écrit par script : ELEC-b-001 et ELEC-b-002 sont retenus sur la cause LUE dans le code, preuve en direct à refaire sur un calepinage dessiné.
## 7. Optionnels (S4 ou hors tâche)
ELEC-a-013 (accords « 1 chaînes », « 1 modules », « 1 onduleur(s) ») ; ELEC-a-014 (nom d'onduleur doublé et coupé, carte Onduleur) ; ELEC-b-007 (message « provenance » sous le
champ Dispositif ; bouton « Ajouter une plage » qui déborde de 13 px). Renvoyés au lot E (maquettes) : barre de progression des 5 étapes absente, ligne « Module posé » en double
sous le menu de l'étape Panneaux (ACAL1298 PROCHE). Non tâché : « Proposer le tracé » sans position d'onduleur (aucune position enregistrée, D-ACAL-70) ; `/proposal`, moteur de devis et prix : hors périmètre L5 (aucun constat du lot).
