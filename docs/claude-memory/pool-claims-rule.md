# Pool partagé « work on all plans » : claims minimales, tâches maximales, débloquantes d'abord

**Règle fondateur (Reda, 10/10/2026, session dev-all-laptop).** Quand plusieurs sessions drainent le pool en même temps :

1. **Minimiser les claims** : ne prendre que `file:` + `app:` des lanes que l'on DISPATCHE, lane par lane (jamais un bloc de
   fichiers « au cas où ») ; une lane finie et foldée garde sa claim seulement jusqu'au merge de la vague (D-CLAIMS-MERGE :
   relâcher au fold a fait reconstruire 7 tâches sur l'autre PC) ; tout le reste est relâché aussitôt.
2. **Maximiser les tâches** : un agent = une lane entière (5-15 tâches), 8 agents, et re-planifier à chaque wake pour remplir
   les lanes libérées ; la vague se merge à 60-80 tâches (jamais moins sans accord explicite du fondateur).
3. **Débloquantes d'abord** : à planification égale, dispatcher en premier les tâches qui sont cibles d'`@after` d'autres
   tâches ouvertes (contrats PACT10, têtes de chaîne, `cgv_imprimees`-like) — classer les candidates par nombre de dépendants
   ouverts (le planner JSON donne `deps` ; compter les inverses) ; une tâche dont un `@after` vise une tâche ENCORE OUVERTE
   dans une autre PR ne se dispatche pas (elle refusera à bon droit).

**Pourquoi :** 10/10, les claims larges d'un poste ont bloqué l'autre, et les claims relâchées trop tôt ont produit des doublons ;
les deux coûtent une vague.
