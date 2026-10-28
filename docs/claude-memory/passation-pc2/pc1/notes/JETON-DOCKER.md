# JETON DOCKER — un seul usage lourd de la pile locale à la fois (ordre fondateur, Reda, 27/10/2026 20:00 Casablanca)

« similar to the jeton you are using for CI you should have one for docker and make sure docker is well used — the
whole machine is clogged »

## Règle
1. **Un seul détenteur à la fois** pour tout usage LOURD de la pile locale :
   - le harnais `scripts/test-backend.ps1` (base de test partagée `test_erp_db`), quel que soit le module ;
   - tout `docker compose run … manage.py …` de rendu réel (PDF, devis auto, migrate, recapture de goldens) ;
   - `seed_demo`, `migrate`, `loaddata`, une recapture `UPDATE_GOLDEN=1`.
   La coordinatrice le donne par message « JETON DOCKER <CODE> » ; le détenteur fait UNE passe (tests du seul module
   touché ou le rendu prévu), note le résultat, et rend le jeton par message (« jeton docker rendu »).
2. **Sans jeton, zéro conteneur lancé** : tests purs seulement (`SimpleTestCase`, `unittest` sans base, `node --test`,
   vitest sur UN fichier), flake8 / check_* / eslint / `astro check`. La CI du run `merge_group` reste le gate.
3. **Conteneurs de développement** (`sleep infinity`, `… -run-…` de pip/shell) : **arrêtés dès qu'on ne s'en sert pas**
   (`docker rm -f <nom>`). Un conteneur `run` qui dépasse 20 min sans sortie est à tuer par son propriétaire.
4. Jamais `docker compose restart` / `down` sur la pile partagée (CORC = gardienne de la pile) ; jamais la base de dev
   redémarrée (elle vient de passer 1 h en récupération).
5. **Au-delà de Docker** : la machine sature surtout côté hôte (node/vite/vitest/astro, python, git sur un disque à 82
   worktrees). Un `astro dev` / `vite` maximum par session, fermé après le rendu ; pas de `git worktree add` (disque)
   — construire dans son propre worktree ; une seule critique Fable en vol par session.

## Détenteur actuel
- **CPDF** (2e fenêtre ≤ 45 min : 7 modules PDF lourds + rendus r3, depuis 22:30 UTC).
- File : CSV (rejeu réel vague 2, ~40 min) → RPDF (round 2 : 8 modules + 30 PDF + recapture goldens, ~45 min) → RSIZ (re-rendu 8 devis) → AGC (rendu pompage) → AGV (rendu parcours agricole après merge 0144) → sur demande.
- Rendus : RHOR 19:38 ; CPRS 20:44 ; CPDF 21:28 ; RPDF 22:08 ; AGV 22:28 (211 tests OK, 7 modules).
- ATTENTION goldens : toute nouvelle clé i18n (table de libellés embarquée) fait bouger les 104 build_quote_data + 21 legacy, toutes familles. RPDF (#1114) atterrit d'abord ; CPDF/AGC recapturent ensuite une fois, sur main.
