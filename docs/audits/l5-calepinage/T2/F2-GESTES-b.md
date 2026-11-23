# F2-GESTES-b — contre-vérification (tour 2, 23/11/2026, bureau 1440 × 900, clair ; sombre pour le schéma)

Compte `rev_b2`, pile `l5cal` (origin/main@bfb859c90). Captures : `scratchpad/T2/F2-GESTES-b/cap/`. Verdicts : `registre/evenements/T2-F2-GESTES-b-cv.jsonl`.

## Verdict en trois lignes
Sur 17 corrections : 9 `ok`, 6 `partiel`, 1 `non-fait`, 1 non essayée ; aucune régression, aucun constat « faux ».
Les `partiel` sont des corrections qui marchent à moitié sur le vrai parcours (caméra trop reculée, épingle jamais rendue, tableau des pans, Total en double, calepinage rapide non marqué à la création, croquis illisible).
ACAL384 (base visuelle) n'existe plus sur `main` : fichier et images supprimés par 2c50ab2d89, jamais ré-ajoutés.

## Comptes
ok 9 · partiel 6 · non-fait 1 · faux 0 · régression 0 · déjà-présent 0 · non essayé 1. Aucune matrice de classe jouée (liste de contre-vérification seule).

Pas `ok` :
- **ACAL956 partiel** : le toit entier est dans le cadre, mais zoomé en arrière sur un toit de maison (≈ 75 px sur 967 px de carte, contre 450 px au tracé) : `zoomToFitRing` est plafonné à 19.
- **ACAL972 partiel** : épingle masquée à la fermeture (ok), mais après « Effacer » il n'y a plus aucun marqueur : elle ne revient pas.
- **ACAL981 partiel** : « Bâtiment 1 » ok ; « contour du pan non tracé » reste dans « Site — pans de toit et surfaces de pose » d'un toit tout juste fermé (aire « — » alors que l'en-tête dit 61 m²).
- **ACAL994 partiel** : la carte lit le chiffre servi (4 636 kWh/an, « au dernier enregistrement ») mais le Total « Production estimée » et la ligne « Année 1 » montrent 4 362 (calcul navigateur), puis 6 355 en Résultats.
- **ACAL1006 partiel** : adoption d'un calepinage ouvert vide → `rapide` ok ; création depuis un devis automatique (la preuve du plan) → `complet`, car ce devis porte déjà un `roof_layout` `{result, scenario, panelWatt}`.
- **ACAL1028 partiel** : croquis présent, légende exacte, au-dessus de la liste ; mais bande de 235 × 22 px à 60 % d'opacité, libellés rendus à ~3 px (maquette : schéma pleine largeur). Moitié « le vrai schéma remplace le croquis » non essayée.
- **ACAL384 non-fait** : `frontend/e2e/calepinage-visuel.spec.js` et ses 8 images absents de `origin/main`.

`ok` : ACAL958, 975, 962 (moitié « pays réglé » non essayée), 965, 993, 1007 (défauts de finition au registre), 987 (voir ci-dessous), 967, 478 (spec et relevé non rejoués, 5 étapes constatées à l'écran).

ACAL987 : rejeu manuel de l'oracle sur les 43 onglets d'un calepinage enregistré non simulé : 0 réponse 5xx, 0 erreur d'onglet, 0 `console.error` hors tuiles ; seul écart un GET `plan-importe` → 409 sur 15 onglets, causé par le document d'exemple du contrat (plan de fond n° 512 non rattaché). Motif serveur « Conception enregistrée — il manque le calcul » confirmé.

## Constats neufs (`registre/constats/T2-F2-GESTES-b.jsonl`)
- 001 S3 : tracé fantôme et phrase de refus en double après une allée refusée.
- 002 S4 : bandeau « Conception rapide » doublé, tronqué, bouton 36 px (K7).
- 003 S3 : « J'ai vérifié le toit » sur plan vide déclenche un /simuler en 409 + console.error.
- 004 S4 : « Surface du toit » affiche 30 m² avec 4 coins posés, 61 m² après « Terminer ».
Aucun S1-S2 neuf.

## Ce qui est bien
Masquage de l'épingle à la fermeture ; fenêtre « Déplacer les panneaux » visible tout de suite et après pente/plat ; gain bifacial retiré sur la pente seulement ; refus d'allée en français sans clé ; refus « pas de facture » dit une fois avec un lien de 44 px ; bloc `chiffrage` servi (ouverture et enregistrement, `non_servi` sans lead) ; copie « Calepinage (copie) chargé » et empreintes à 8 caractères.

## Non essayé
- ACAL1315 : spec de comparaison des 13 maquettes (suite Playwright du dépôt sur pile semée, hors règle de lecture seule du code) — à jouer par l'orchestrateur.
- ACAL962 moitié « pays réglé » : exige de modifier les réglages partagés de la société.
- ACAL1028 moitié « fiches complétées » : 11 champs de fiches équipements à saisir.
- Fond de carte : gris sans photo (fiche de l'instrument) ; la boîte noire vue sur le toit 3D fermé (étiquette sans glyphes ?) n'est pas jugée.

## Trois propositions
1. **Cadrage à la fermeture** (référence : Aurora Solar, Reonic) : plafond de zoom relevé comme `cadrageAnneaux zoomMax` de l'atelier ERP pour que la maison remplisse ~60 % de la carte.
2. **Un seul chiffre de production par écran** (référence : PVsyst, rapport unique) : faire lire par le Total et « Année 1 » le même bloc `chiffrage`, avec « estimation » partout ailleurs.
3. **Schéma unifilaire grisé pleine largeur** (référence : OpenSolar, illustration de schéma avant données) : le croquis dans la zone centrale à la taille de `Schema.dc.html`, pas dans le rail de 270 px.
