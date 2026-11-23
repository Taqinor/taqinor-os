# T3-POSE — contre-vérification du tour 3 (compte rev_b4, bureau 1440 × 900 clair)

Fichiers : registre/evenements/T3-POSE-cv.jsonl, registre/constats/T3-POSE.jsonl. Captures : scratchpad/T3/T3-POSE/cap/.

## Comptes
24 verdicts : 10 ok, 11 partiel, 3 non-fait, 0 faux, 0 régression. Les verdicts hors `ok` sont dans le jsonl avec leur « reste ».

## Défauts qui comptent
- T3-POSE-004 (S1) : une pose de 16 panneaux faite par « Remplir automatiquement » (cible 5) s'enregistre à 16, se rouvre à 5 sur la carte et dans « Pose actuelle », et un simple « Enregistrer » sans geste écrase le serveur à 5. Les poses de 60 (châssis) et 27 (« Le plus de panneaux ») se rouvrent intactes : le cas D-ACAL-75 n'est donc reproduit aujourd'hui que pour une pose personnalisée plus grande que la cible.
- T3-POSE-001 (S2) : le bouton Annuler de la barre du plan s'allume mais ne défait pas le coin glissé (Ctrl+Z oui).
- T3-POSE-002 (S2) : « au plus 16 panneaux » alors que « + » en pose 20 (ACAL1618).
- T3-POSE-007 (S2) : les retraits saisis (0,8 m sur 3 × 1,5 ; 2 m sur 10 × 7) ne changent ni la pose ni le balayage.

## Non essayé (temps, ou pile)
ACAL1527, ACAL1528, ACAL1529 (sélection de panneaux au geste sur la scène 3D impossible à produire : aucun panneau sélectionné), ACAL1443, ACAL1519, ACAL1411, ACAL1429, ACAL1424, ACAL1427 (pas d'onglet Schéma ni de fiche incomplète choisissable), DC-historique-pan-et-surfaces, DC-2, DC-3, DC-4, DC-5, DC-6.
Non essayé (pile) : géocodage de « Localiser » (ACAL1410), simulation à jour (ACAL1612).
Le recalcul d'une table de retrait société à 0,80 m (ACAL1504) n'a pas été joué.

## Remarques
Session expirée ou connexion limitée deux fois (« Requête ralentie ») ; chargement parfois > 11 s, rejoué.
