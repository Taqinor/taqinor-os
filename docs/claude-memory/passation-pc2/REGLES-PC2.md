# Règles des lanes PC2 — run L3 « générateurs de devis » (28/10/2026, nuit)

Tu es UNE lane (ton CODE est dans ton brief). La coordinatrice PC2 est la session qui t'a démarrée. Dossier
partagé : `C:\dev\pc2-run\` — `passation\` (README, blocs d'état, notes PC1), `etat\<CODE>.md` (TON état, à tenir),
`decisions-prises.txt` (décisions prises pour le fondateur, une ligne par décision, préfixée de ton CODE).

## 1. Ta branche
- Ton worktree est coupé de la branche distante de ta lane (PC1 ne la touche plus : une branche = une machine).
  Tu travailles sur TA branche (celle de ton worktree). Tu ne touches aucune autre branche, jamais le checkout
  principal `C:\dev\taqinor-os` (la pile Docker le monte sur `main`), jamais `git worktree add`.
- Commit par tâche, message en français ; TOUT est commité avant la fin de chaque tour (un crash de l'app tue le
  travail non commité — mesuré sur PC1). Fichiers `_<code>_*.py` / `_<code>_out/` dans `backend/django_core/`
  (recettes de rendu) : jamais commités.

## 2. JETON CI (une seule CI dans toute la flotte, PC1 + PC2 — ordre fondateur)
- **Tant que la coordinatrice ne t'a pas envoyé « JETON <CODE> »** : tu construis, tu testes, tu rends la critique
  Fable, tu prépares la PR. Quand TOUT est prêt (contrôles hôte verts, Fable rendue, `main` fusionné), tu peux
  faire UN push « léger » et `gh pr create` SANS auto-merge (la CI PR des branches `claude/*` saute les jobs lourds —
  CI-UNE). **Tu ne mets RIEN en file** (`gh pr merge --auto` INTERDIT sans jeton) et tu ne re-pousses pas « pour voir
  la CI ».
- **Avec « JETON <CODE> »** : `git fetch && git merge origin/main` (conflit attendu sur le DONE LOG de
  `docs/plans/PLAN_AUDIT_*.md` ou `docs/WEB_PLAN.md` → garder les DEUX côtés ; `docs/CODEMAP.md` → garder les deux
  puis `PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --write`), contrôles hôte, UN push,
  `gh pr merge <n> --auto --merge`, puis tu suis ta CI jusqu'à MERGED (`powershell -File scripts/watch-ci.ps1 -Pr <n>`).
  Un rouge = UN push correctif sous le même jeton, après la fin de TOUS les shards. Une éjection de la file (drapeau
  auto-merge disparu, checks PR verts) = les goldens ont bougé sur `main` : re-fusionner `main`, recapturer, UN push,
  re-armer. Au MERGED, tu termines ton tour par « MERGED #<n> » (la coordinatrice passe le jeton).
- Contrôles hôte avant tout push : `flake8 --max-line-length=120` + `py_compile` sur les .py touchés ; `eslint` sur
  les fichiers front touchés ; `python scripts/check_stages.py` ; `PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --check` ;
  `python scripts/check_ownership.py` ; `python scripts/check_forme_code.py --base origin/main` ;
  `python scripts/check_api_shapes.py` si une vue/contrat a bougé ; `cd apps/web && npx astro build` si apps/web a bougé.
  Jamais `scripts/preflight.ps1` (règle fondateur 27/10).

## 3. JETON DOCKER (local PC2 — un seul usage lourd de la pile à la fois)
- Usage LOURD = harnais `scripts/test-backend.ps1`, tout `docker compose run … manage.py …` (rendu réel, recapture
  `UPDATE_GOLDEN=1`), `seed_*`, `migrate`, conteneur sans montage. **Sans « JETON DOCKER <CODE> » : zéro conteneur
  lancé** — tests purs seulement (`SimpleTestCase`/unittest sans base, `node --test`, vitest sur UN fichier, flake8,
  check_*, eslint, tsc, `astro build`).
- Avec le jeton : UNE fenêtre (durée annoncée dans ton brief), puis tu termines ton tour par « jeton docker rendu ».
  Conteneurs `run-…` / dev tués dès qu'inutiles (`docker rm -f`). Jamais `docker compose restart`/`down` sur la pile,
  jamais `migrate` sur la base de dev `erp_db` (la coordinatrice l'a migrée au niveau de `main` ; vos migrations de
  branche ne s'appliquent qu'au harnais de test `test-backend.ps1 -RestoreDb`, base `test_erp_db` clonée du template).
- Rendu depuis TA branche : la pile monte le checkout principal, pas ton worktree. Depuis TON worktree :
  `docker compose -p erp-agentique run --rm --no-deps -T django_core python manage.py shell -c "exec(open('_x.py').read())" < /dev/null`
  (script posé dans `backend/django_core/`, tout dans `transaction.atomic()` + `set_rollback(True)`). Jamais `shell < script`
  (bloque sous Git Bash). Un rendu PDF fidèle passe par `builder.generate_premium_devis_pdf` → `registre_renderers()`
  (recette : `passation/notes/CPDF-recette-rendu.md`) — jamais `generate_premium_pdf(build_quote_data(...))` seul.
  Parcours écran : conteneur sans montage (recette `passation/notes/csv-notes.md`) + `VITE_API_URL=http://localhost:<port> npx vite --port <p>`.

## 4. Machine (16 Go, partagée par 5-8 sessions)
- Un seul `vite`/`astro dev` par session, fermé après usage (`taskkill`) ; une seule critique Fable en vol par session
  (sous-agent `Agent` avec `model: fable`, `effort: high`, lecture seule ; les autres sous-agents : `sonnet`/`haiku`
  explicites, jamais sans `model`) ; pas de `vitest` complet (un fichier à la fois) ; pas de `npm run check` sur
  apps/web (> 20 min) — `npx tsc -p tsconfig.check.json` + `npx astro build` suffisent.
- Si tu es arrêtée par la coordinatrice (RAM), tu reprends au message suivant depuis ton dernier commit.

## 5. Règles de fond (CLAUDE.md, toutes en vigueur)
- Règle #4 : `/proposal` seul chemin PDF client ; le moteur ne change jamais un statut. `Produit.prix_achat` jamais
  côté client. Devis envoyés intouchés : toute correction de chiffre du 27/10+ gardée par
  `regles_au_moins(devis, REGLES_CORRIGEES_2710)` (= 3), JAMAIS `calcul_corrige`.
- Rien d'incertain ni d'interne côté client (pas de « estimation » hors étiquettes du noyau, « à confirmer »,
  « selon site », « (moteur C&I) », codes de décision). Données catalogue = fondateur, jamais inventées.
- Fichiers ≥ 2 000 lignes : aucune croissance nette ; tests dans le module de test existant ; ancres `fichier::symbole` ;
  tâches v3 cochées `[x]` + DONE LOG dans le plan propriétaire (`docs/plans/PLAN_AUDIT_*.md` / `docs/WEB_PLAN.md`),
  jamais CODEMAP §10 pour ces fichiers.
- **Ne rien demander au fondateur** : option recommandée, ligne « <CODE> : Décision prise pour le fondateur (à revoir) : … »
  dans `C:\dev\pc2-run\decisions-prises.txt` ET dans ton DONE LOG, et tu continues.
- Le run s'arrête au merge : aucun déploiement, jamais `wrangler`, jamais d'écriture en prod.

## 6. Ton fichier d'état `C:\dev\pc2-run\etat\<CODE>.md` (mis à jour à chaque fin de tour)
```
ETAT: <CONSTRUIT|TESTS|DOCKER-EN-COURS|PRET-PR|PR-OUVERTE #n|EN-FILE #n|MERGED #n|BLOQUE: raison>
BRANCHE: <nom> @ <sha court>  PR: <#n ou aucune>
FAIT: … / RESTE: … / ATTEND: <JETON CI | JETON DOCKER | PR #n mergée | rien>
DECISIONS: (prises pour le fondateur, à revoir)
```
Chaque fin de tour : dernière ligne de ta réponse = une phrase d'état claire (la coordinatrice la lit), commençant par
ton CODE, par ex. « CSV : PRET-PR, attend JETON DOCKER pour le rejeu (40 min) ».
