# T3-TOIT — contre-vérification du tour 3 (compte rev_b3, bureau 1440 × 900 clair)

Joué entre 11 h et 12 h 35 UTC sur la pile l5cal (instrument très chargé par moments : plantages de page et connexions ralenties, rejoués).

## Comptes (33 tâches)
Voir `registre/evenements/T3-T3-TOIT-cv.jsonl` (un verdict par tâche, preuve et capture).

- ok (12) : ACAL1405, 1406, 1273, 1436, 1510, 1329, 1416, 1430, 1431, 1513, 1248, 1420
- partiel (13) : ACAL1275, 1328, 1422, 1423, 1412, 1442, 1409, 1441, 1341, 1408, 1515, 1516, 1421
- non-fait : ACAL1345 (choisir un pan écrit encore un brouillon PUT et marque « Modifications non enregistrées »)
- non essayé (temps / compte / réglage société) : ACAL1323, 1247, 1246, 1418, 1432, 1433, 1503
- faux / régression / déjà-présent : 0

## Les trois défauts graves du tour 2
- ACAL1404 « Pan existant » : se rouvre — case cochée, année 2019, « Zone 1 · Existant 2019 » en liste, dans le tableau par pan et dans « Site » (cal 2063). TIENT.
- ACAL1412 champ au sol compté deux fois : le contour enregistré en champ au sol remplace le pan de tracé (une seule surface « Champ au sol 1 · 7 modules ») ; le devis 50 vs 106 n'a pas pu être joué (409 module_substitue). TIENT sur la surface, devis non prouvé.
- ACAL1510 toit 4 pans à 0 panneau : pose 4 modules, Enregistrer sans 409, simulation lancée. TIENT.

## Non ok (détail)
- ACAL1345 non-fait ; ACAL1341 : document plat avec pitchDeg 22 ; ACAL1423 : épingle non reposée sur calepinage rouvert ; ACAL1328 : cotes masquées sous le toit en Plan normal ; ACAL1442 : étiquettes à gauche des champs, sélecteur Module du pan hors panneau ; ACAL1408/1515/1516 : panneaux noirs (0,0,0) partout (Chromium et WebKit), teinte non visible sur cette pile ; ACAL1421 : ligne « Image : … » absente ; ACAL1275 : message de résultat du devis non vu ; ACAL1409 : hauteur absente ; ACAL1441 : tailles non mesurées ; ACAL1422 : 36 % de la largeur (58 % de la zone libre).

## Non essayées (temps)
ACAL1323, ACAL1247, ACAL1246, ACAL1418, ACAL1432, ACAL1433, ACAL1503 (détail dans le fichier de verdicts).

## Défauts bloquants
Aucun bloquant ; croisés : carte d'adresse qui recouvre le tracé (T3-T3-TOIT-001), 3D plantée sur 20 panneaux.
