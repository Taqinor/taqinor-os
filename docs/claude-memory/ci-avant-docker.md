---
name: ci-avant-docker
description: Règle de Reda pour tout travail (10/10/2026) — la CI vérifie EN PREMIER ; Docker local seulement en parallèle d'un run CI déjà lancé, jamais à sa place
metadata:
  type: feedback
---

**Règle (Reda, 10/10/2026) : « dont use docker instead of CI, CI is always the first to try, you only
can try docker in parallel » — « keep this as a rule for all my work ».**

- Toute vérification part D'ABORD en CI : pousser la branche / ouvrir la PR (au besoin une PR
  jouet en brouillon) et lire les logs CI.
- Docker local seulement EN PARALLÈLE d'un run CI déjà lancé — jamais à sa place, jamais comme
  gate avant de pousser, jamais « monter la pile d'abord ».
- Exception : ce que la CI ne sait pas faire (acceptation en direct 3-bis sur la pile locale) se
  joue APRÈS le push, en parallèle de la CI.

**Why:** 4ᵉ rappel du même genre (15/07, 31/08, 01/09, 10/10). Le 10/10, des suites que la CI
jouait déjà ont été rejouées en conteneurs jetables, et la pile partagée a été montée puis réparée
(conteneur db recréé, redémarrage de Docker Desktop) pendant ~1 h avant de pousser ; la CI
(~2-10 min sur le chemin chaud) aurait répondu plus vite.

**How to apply:** avant de lancer une commande `docker`, se demander si un run CI couvre déjà la
question ; si non, pousser d'abord, puis seulement lancer Docker à côté.
