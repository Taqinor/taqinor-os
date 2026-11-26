# Liste « pluriannuel » montrée au fondateur (ACAL1252, D-ACAL-64) — 26/11/2026

Demande de Reda (26/11) : voir la liste des rapports d'étude et diagrammes remis en mode pluriannuel avec leurs énergies
multipliées par le nombre d'années, AVANT toute re-simulation.

**Exécution** : le 26/11/2026 vers 15 h 45 UTC, sur la production (commit bfe152adc), en lecture seule — le code de la branche
`lot8/liste-pluriannuel` (53650c2d2 : `services/annee_moyenne.py::lister_pluriannuels` et le lecteur `_entrees` de la
commande `acal_dryrun_annee_moyenne`) joué dans un shell Django, à l'intérieur d'une transaction `READ ONLY`, avec un
garde qui refuse toute requête autre qu'une lecture. Rien n'a été écrit, aucune commande de gestion lancée.

**Résultat** : `{"lus": 4, "concerne": 0, "indetermine": 0}`

- 4 résultats de simulation enregistrés ont été lus (calepinages et variantes, toutes sociétés).
- **0 document concerné** : aucun rapport ni diagramme remis ne porte des énergies multipliées par N.
- 0 cas indéterminé.

**Conséquence** : rien à réparer en production. La commande reste disponible après le déploiement du lot 8 :
`python manage.py acal_dryrun_annee_moyenne --dry-run [--company <id>] [--json]`.
