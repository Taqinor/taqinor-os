# Lot O — consolidation du tour 3 et des contrôles d'après L5 (23/11/2026)

Dernière lecture du registre : `date -u` = 13 h 18 UTC ; dernier fichier du tour 3 modifié à 12 h 48 UTC (`T3/B3.md`) ;
lus : 49 constats `T3-*.jsonl` (1 S1, 14 S2, 29 S3, 5 S4), 163 verdicts `T3-*-cv.jsonl` (73 ok, 59 partiel, 8 non-fait, 9 non-essayé,
6 PROCHE, 6 ÉLOIGNÉ, 2 NON-COMPARÉ), `T3/audit-ok.md` (48 confirmés, 14 insuffisants, 2 contredits), C1, C2, C3, `entree-lot-O.md`.

## 1. Comptes
- Tâches du plan CALEPINAGE (`lot-O-taches.md`) : **84** — M0 2 · M1 23 · M2 57 · GATED 1 · acceptation 1. Ids : ACAL1900-1913 (14) et
  ACAL1950-1958 (9) = les lanes de reprise et « moteur-unique » ; ACAL1914-1949 (36) et ACAL1959-1983 (25) = neuves, sans trou.
- Neuves par gravité : S1 0 (ACAL1900 est S1 mais déjà donnée) · S2 7 (1914, 1915, 1949, 1965, 1976, 1974, 1961 selon le fichier) · S3 le reste.
- Tâches d'autres plans (`autres-plans.md`) : **12** — lead 1 (ALEA67), devis 7 (ADEV123-128 dont 3 GATED), parametres 1 (APAR92,
  GATED), stock 1 (ASTK265), transverse 3 (ADEV121, ADEV122 GATED, ADEP107). ALEA67 est écrite telle que la lane la construit.
- Doublons écartés : T3-T3-TOIT-001 = T3-T3-ECRANS-001 (→ ACAL1904) · T3-PROD-009 et ACAL1538 non fait = ACAL1954 (D-ACAL-91) ·
  ACAL1608 (reste) = la ligne ouverte d'ACAL1608 · ACAL1315 = ACAL1748 · ACAL891 = ACAL1758 · ACAL385 → acceptation ACAL1975 ·
  ACAL1709 reste bloquée sur ACAL1001 · C1-T1→ACAL1955, T2→1950, T3→1951, T4→1952, T5→1954 (+ ADEV121), T6→1953, T7→1956, T8→ADEV122 · demandes croisées déjà honorées
  (commits `a8c282f0b3`, `9c9fb8a8f4`, `bfca161a41`, `7b1904c095`, `0f966a940d`, `4723a164ce`) écartées.
- Classes : aucune fiche neuve ; K-HYDRATATION (ACAL1900, 1909, 1921, 1923, 1926), K-CARTE-OPAQUE-SUR-ZOOM (1904, 1907, 1976) et K-JARGON
  (1928, 1938) sont des violations de classes du tour 1 : à compléter par l'orchestrateur (`T2/classes/complement-O.md`, non écrit ici).

## 2. Décisions citées
D-ACAL-75 (ACAL1900) · 80 (ADEV122) · 82 (ACAL1968) · 83/84/85 (lignes existantes, non touchées) · 89 (ACAL1955) · 90 (ACAL1956) · 91
(ACAL1954) · 92, 93, 94 (ADEV125-127, `taches: []` à renseigner dans `decisions.yml`) · 95 (APAR92, idem). Aucune décision neuve.

## 3. Fichiers partagés entre tâches (disjonction des lanes — `plan_lanes.py` fond tout en UNE lane de 65 tâches)
`50-coque-atelier.css` 1904, 1906, 1907, 1976, 1977, 1978 · `optimizer.ts` 1902, 1903, 1919, 1920, 1970 · `electrique.py` 1915, 1952,
1953, 1954, 1973 · `roof-tool-pro11.ts` 1900, 1902, 1916, 1926 · `zones.ts` 1920, 1925, 1964, 1980 · `selectors_calepinage.py` 1950, 1951,
1967 · `layoutEditor.ts` 1900, 1901, 1945 · `EtapePanneaux.jsx` 1914, 1917, 1981 · `calepinage_resultat.json` 1915, 1933, 1956 ·
`51-etape-toit.css` 1907, 1925, 1942 · `EtapeToit.jsx` 1922, 1945, 1971 · `ResultatIncomplet.jsx` 1934, 1939, 1940. Chaque tâche
porte son `@after` de fichier ; `Files:` de chaque ligne fait foi (181 fichiers, tous au propriétaire calepinage).
Fichiers ≥ 2 000 lignes qui ne grossissent pas (net ≤ 0, extraction nommée) : `roof-tool-pro11.ts` 4 357, `electrique.py` 3 990, `optimizer.ts` 2 010,
`layoutEditor.ts` 2 996, `chaine_pertes.py` 2 440, `simulation.py` 1 974 (proche), `batterie.py` 2 108.

## 4. Preuves à rejouer (cas non joués, ni défaut vu ni tâche)
ACAL1410, 1525, 1526, 1533 (poses) · 1604 heures écrêtées, 1622 (tuer le worker), 1249 (devis antérieur à X4) · 1708, 1831, 1832, 1617,
DC-PVGIS-PERTES-EGALES, DC-ECART-DEVIS-SIGNE (résultat COMPLET : aucun sur la pile avant ACAL1968) · 1340, 1267 · 1343 (délai < 5 s sur pile au repos),
1417, 1337 (4 chaînes), 1703 (ligne Pertes), 1543 (avant/après devis) · 1412 (devis 50 contre 106, 409 `module_substitue`), 1409 (hauteur),
1441 (44 px, sombre), 1421 (ligne « Image »), 1408 / 1515 / 1516 (teinte des panneaux : GPU), 1323, 1247, 1246, 1418, 1432, 1433, 1503 ·
ACAL1810 (rechargement hors ligne, WebKit refuse) · ACAL1604 · ACAL987 (409 `plan-importe`, `console.error`) · 14 « insuffisants » de
`audit-ok.md` · cas « plan sans emplacement » d'ACAL1530 · onduleur « Huawei 10 kW » devenu « à désigner » sans geste (T3-B3-007, catalogue partagé ?).

## 5. Optionnels (S4, sans tâche)
T3-T3-ECRANS-006 (`?onglet=production` s'ouvre sur l'éditeur du Toit) · -009 (barre d'outils coupée à 390 px) · T3-B3-008 (deux boutons dorés v1 / v2),
-009 (traits de progression dorés selon les étapes faites), -010 (double anneau de focus « Précision ») · ACAL1612 (Total sans « estimation de
l'atelier ») · ACAL1422 (36 % de la largeur de carte, 58 % de la zone libre) · ACAL1543 (cinq « Régler » sombres à la fois) · ACAL1829 (légende
sans bornes chiffrées, « De la consommation » contre « De la facture ») · ACAL1833 (tête « Étape 4 sur 5 » : +88 px) · T3-T3-TOIT-003 (3D plantée,
rendu logiciel) · `PhotoSiteCalage.jsx` (champ fichier natif), `ParcoursDuPan.jsx` (`sm:grid-cols-2`) · page privée `/preview/toiture-3d-pro-11`
du site public : neuf retouches d'atelier sans tâche (à dire à Reda).

## 6. Non couvert
- Fidélité aux maquettes v2 (`T3/B3.md`) : 0 FIDÈLE, 6 PROCHE, 6 ÉLOIGNÉ (Documents, Démarrage rapide, Tablette, Téléphone relevé, Téléphone client,
  Présentation) : refonte d'écrans entiers, non planifiée ici (groupe d'écrans, pas un défaut) ; seuls les défauts chiffrés de B3 (001-007) ont une tâche.
- Journal du serveur en avance d'une heure (base de fuseaux antérieure au décret du 20/09/2026) : à vérifier sur l'image de prod AVANT toute tâche (plan deploy).
- Lecture d'une consigne du lot : C2-T4 (forme horaire) est écrite ; la CLASSE tarifaire d'un lead C&I n'est pas écrite (correspondance à valider).
- Le texte « d'où il vient et où il va » du journal d'ACAL1955 et le nom du contrat d'ACAL1950 sont des propositions : la lane peut les renommer.
- Vérificateurs T3-TOIT et T3-ELEC : rapports lus à 13 h 18 ; les 7 tâches non essayées de T3-TOIT restent des preuves à rejouer.
