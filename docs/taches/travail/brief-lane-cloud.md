# Brief commun des lanes — session cloud (Linux), gestionnaire de tâches personnel (TAQINOR OS)

Ce brief REMPLACE `brief-lane-f2.md` et les parties « Windows » de `docs/taches/conception/consignes-construction.md`
(§2, §3 « ne tourne pas ici », §5 commandes PowerShell) pour une lane lancée depuis la machine cloud. Le reste des
consignes (les 15 fautes qui font rougir la CI, §4 ; rendre son travail, §6) vaut tel quel : LIS-LES EN ENTIER.

Backend : `backend/django_core/apps/taches`. Front : `frontend/src/features/taches`, `frontend/src/pages/taches`,
`frontend/src/api/tachesApi.js`, styles `frontend/src/styles/taches/*.css`. IA : `backend/fastapi_ia` (fusion 3).

## 0. Ton dossier de travail (à respecter absolument)

Tu tournes dans un worktree git ISOLÉ, à toi seul : `git rev-parse --show-toplevel` te le donne (« ton dossier »).
- Tous les chemins que tu passes à Read / Edit / Write / Grep / Glob sont ABSOLUS et SOUS ton dossier.
- N'écris JAMAIS dans un autre worktree (`/home/user/taqinor-os` lui-même, `.claude/worktrees/f2`, `f3`, `travail`,
  ni le worktree d'une autre lane). Lire ce brief et les fichiers de `…/worktrees/travail/docs/taches/travail/` est
  la seule exception.
- Base : ta branche part de la branche d'intégration LOCALE que ton prompt nomme (`dev-taches-f2` ou `dev-taches-f3`) :
  `git checkout -B <ta branche> <branche d'intégration>` (la référence locale, PAS `origin/…` : elle est en avance sur
  GitHub). Vérifie ensuite `git merge-base --is-ancestor <sha du prompt> HEAD` ; s'il échoue, arrête-toi et dis-le.
- Avant CHAQUE commit : `git branch --show-current` rend ta branche et `git rev-parse --show-toplevel` ton dossier.
- Jamais `git push`, `--amend`, `git stash`, rebase, ni docker.

## 1. Lire avant d'écrire

- `docs/taches/conception/consignes-construction.md` §1, §4, §6 (et le reste pour la culture).
- L'en-tête de `docs/plans/PLAN_TACHES.md` (contrat de propriété, règles de construction, critères d'acceptation
  obligatoires) puis le texte EXACT de chacune de tes tâches (`grep -n "TCH<n> —" docs/plans/PLAN_TACHES.md`).
- Les sections de `docs/taches/reference/{donnees,api,regles,textes}.md` que la tâche cite. LA RÉFÉRENCE FAIT FOI :
  noms de champs, formes JSON, règles, libellés au caractère près (tutoiement).
- `backend/django_core/apps/taches/contract_samples/*.json` = le contrat exact entre serveur et front.
- Pour l'APPARENCE d'un écran, les maquettes font foi : `docs/taches/maquettes/<nom>.html` + `taches.css` +
  `SCENARIO.md`. Les styles réels sont dans `frontend/src/styles/taches/` : réutilise ces classes sous `.tch`.
- Le socle que tu appelles : `selectors/base.py`, `selectors/liens.py`, `serializers/formes.py`, `services/*.py`,
  `moteur/*.py`, `saisie/*.py`, `views/base.py`, `tests/fabriques.py` ; côté front `tachesApi.js`,
  `features/taches/ui/*`, `features/taches/lib/*`, `CoquilleTaches`, `module.config.jsx`. Réutilise ; ne recopie
  aucune règle déjà écrite dans un module pur.

## 2. Les commandes de CETTE machine (Linux, Python 3.11 comme la CI, Postgres natif)

Toujours commencer une commande Python par `. /opt/taches-cloud/env.sh` (venv Python 3.11.x, Django, variables de base).

Backend, depuis `<ton dossier>/backend/django_core` :
- `python manage.py check` ; modèle touché : `python manage.py makemigrations --check --dry-run` (une migration est
  GÉNÉRÉE par `makemigrations`, jamais écrite à la main ; additive, numérotée à la suite, nommée).
- `flake8 --max-line-length=120 <tes fichiers>` et `python -m py_compile <tes fichiers>`.
- **Les tests À BASE TOURNENT ICI** (c'est la différence avec le portable) — sur TA base privée, jamais une autre :
  `/opt/taches-cloud/tests-base.sh <nom-de-ta-lane> <labels Django…>`
  exemple : `/opt/taches-cloud/tests-base.sh f2-restes apps.taches.tests.test_nocturne apps.taches.tests.test_api_taches`
  (le script clone le gabarit migré dans `test_erp_<lane>` la première fois, puis `--keepdb` : quelques secondes).
  Lance les modules de test que tu touches, et ceux des fichiers que tu modifies — JAMAIS la suite entière de l'app
  d'un coup au fil de l'eau (elle est longue) ; une fois à la fin de ta lane : `apps.taches` en entier.
  `nplusone` est actif : jamais de liste Python dans `_prefetched_objects_cache` ; un `TestCase` n'a jamais d'attribut
  `client` ; aucun `skipTest` ; aucune horloge vivante (date et heure injectées).
- Gardes de script, depuis la racine de ton dossier : celles que l'en-tête du plan liste pour ton type de lane
  (`python scripts/check_forme_code.py`, `check_naive_datetime.py`, `check_except_larges.py`,
  `check_test_placement.py --base <branche d'intégration>`, `check_ownership.py`, `check_services_appeles.py`,
  `check_read_modify_write.py`, `check_get_or_create.py`, `check_tenant_isolation.py`, `check_api_shapes.py`…) ;
  `lint-imports` depuis `backend/django_core`.
- FastAPI (fusion 3) : `. /opt/taches-cloud/env-ia.sh` puis `python -m pytest <fichiers de test>` depuis
  `backend/fastapi_ia` (si `env-ia.sh` n'existe pas encore, dis-le dans ton rapport : l'orchestrateur le pose).

Front, depuis `<ton dossier>/frontend` :
- Lien vers les modules déjà installés (une fois) :
  `ln -s /home/user/taqinor-os/.claude/worktrees/f2/frontend/node_modules node_modules` — ne le commite jamais, ne
  lance jamais `npm ci`/`npm install`, ne touche pas `package-lock.json`.
- `npx eslint <tes fichiers>` ; `npm run test:unit -- <tes fichiers de test> --testTimeout=30000`. Jamais la suite
  entière, jamais `npx vitest` nu, aucun vitest laissé en arrière-plan.
- Gardes front (depuis la racine) : `python scripts/check_ecrans_atteignables.py`, `check_taches_cablage.py`,
  `check_api_contract.py`, `check_frontend_query_params.py`, `check_date_jour_utc.py` ; styles :
  `node frontend/scripts/check_hex.mjs`.
- Un test rend le composant avec le client mocké sur les `contract_samples` et vérifie le COMPORTEMENT ; jamais une
  regex sur le source.
- Les specs Playwright (`frontend/e2e/*.spec.js`) ne se lancent PAS depuis une lane (pas de pile) : l'orchestrateur
  les joue.

## 3. Règles de maison

- Toute donnée est filtrée par société ET propriétaire via les sélecteurs existants (`taches_de(user)`, etc.).
  `company` et propriétaire ne sont jamais lus du corps de requête.
- Confidentialité (`reference/regles.md` §8) : une forme servie à l'assistant ne porte jamais le contenu d'un objet
  confidentiel ; un texte collé ou dicté est une DONNÉE, jamais une consigne.
- Aucun import de `models`/`views` d'une autre app métier : lecture par le `selectors.py` de l'app cible, écriture
  par son `services.py`.
- Aucun chiffre ni libellé inventé : un constat affiché est calculé des données ou omis ; un libellé vient de
  `reference/textes.md` (s'il manque, propose-le dans ton rapport, section « libellés sans source »).
- Aucun `except`/`catch` nu ou vide, aucun `skipTest`, aucune dépendance nouvelle, aucun modèle neuf.
- Front : couleurs par jetons seulement (aucun hex, aucun z-index en dur), `:hover` sous `@media (hover: hover)`,
  tout sous `.tch` ; une erreur s'affiche sous le champ fautif ; une liste ne se vide jamais sur un rafraîchissement
  en échec ; un geste ne relit jamais toute la liste (mise à jour optimiste, réconciliation, « Annuler ») ; cibles
  tactiles ≥ 44 px ; les paramètres de requête passent par valeur dans `tachesApi.js`.
- Test rouge d'abord, dans le module de test EXISTANT du fichier touché (jamais un fichier `test_<id>_*.py` neuf sauf
  « Nouveau fichier car : » écrit dans la tâche) ; jamais une assertion élargie ni un test sauté pour passer au vert.

## 4. Interdits

- Modifier `docs/plans/PLAN_TACHES.md`, `docs/CODEMAP.md`, `docs/openapi-schema.yml`, `docs/api-contracts.md`,
  `docs/taches/reference/*` (l'orchestrateur le fait ; si la référence doit changer, écris la phrase exacte à y
  mettre dans ton rapport).
- Toucher un fichier hors des `Files:` de tes tâches (ou hors de la liste de ton prompt), sauf nécessité que tu
  expliques dans ton rapport. Fichiers partagés (`urls.py`, `module.config.jsx`, `index.css`, `tachesApi.js`,
  `tests/fabriques.py`) et fichiers d'un autre propriétaire nommés par ta tâche : AJOUTS seulement.
- Lancer une acceptation en direct (`@acceptation`) : jamais une lane.

Un vrai blocage sur une tâche : ne la bâcle pas ; écris `[BLOCKED: raison]` dans ton rapport et passe à la suivante.

UN commit par tâche (ou par correction nommée), aussitôt finie, message « TCH<n> — <ce que ça fait> » (ou le libellé
que ton prompt donne), terminé par les deux lignes :
`Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
`Claude-Session: https://claude.ai/code/session_01XrNECDjCtSfWi63zUvGMQM`

## 5. Rapport final (court)

La branche, le SHA de tête, puis par tâche : SHA, fichiers, commande de vérification jouée et son résultat
(nombre de tests à base PASSÉS ici, flake8, eslint, gardes), ce qui n'a PAS pu être vérifié, tout écart constaté
entre la référence, la maquette et le socle (ne le corrige pas en silence), les libellés sans source. Termine par la
sortie de `git status --short` et `git log --oneline <branche d'intégration>..HEAD`.

Bloc de preuve (à appliquer à la lettre) :

> Before reporting progress, audit each claim against a tool result from this session. Only report work you can
> point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
