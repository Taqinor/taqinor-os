# Règle fondateur (Reda, 27/10/2026 16:15 Casablanca) — « reduce your number of CI runs »

Contraignante pour toutes les sessions L3 (C&I, résidentiel, agricole) jusqu'à la fin du run.

1. **UNE PR ouverte par session** — toutes les vagues restantes s'ajoutent en commits à cette PR ; jamais une deuxième PR
   tant que la première est ouverte ou dans la file (exception : la 1re PR d'extraction de CPRW, seule et petite).
2. **UN push par round**, seulement quand le round est fini, la critique Fable rendue, et les contrôles locaux verts
   (flake8, `check_stages.py`, `codemap_fingerprint.py --check` ; eslint / `astro build` sur les fichiers web ; le seul
   module de test touché).
3. **Jamais de push « pour voir la CI »**, ni pour un petit correctif qu'on peut grouper.
4. **Pas de commit vide, pas de close/reopen, pas de relance manuelle de run.**
5. **Re-fusionner `main` seulement quand la file vous a éjecté** (entrée UNMERGEABLE disparue / drapeau auto-merge
   disparu) — un seul push alors. Lire la file : `gh api graphql -f query='{repository(owner:"Taqinor",name:"taqinor-os"){mergeQueue(branch:"main"){entries(first:20){nodes{position state pullRequest{number}}}}}}'`
   (`autoMergeRequest` vaut null dès qu'une PR est DANS la file — ce n'est pas un signe qu'elle en est sortie).

Pourquoi : chaque push = un run de 36 jobs ; les machines de test GitHub sont partagées par ~12 PR → un run de file
de merge prend ~50 min. Chaque push évité rend ~50 min à tout le monde.

Rendu PDF C&I/agricole fidèle (jamais le legacy direct) : voir `CPDF-recette-rendu.md` dans ce dossier.
