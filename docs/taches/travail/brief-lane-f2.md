# Brief commun des lanes de la fusion 2 — gestionnaire de tâches personnel (TAQINOR OS)

Backend : `backend/django_core/apps/taches`. Front : `frontend/src/features/taches`, `frontend/src/pages/taches`,
`frontend/src/api/tachesApi.js`, styles `frontend/src/styles/taches/*.css`.
Le socle (fusion 1) existe sur la branche `dev-taches-f2` : modèles, sélecteurs, sérialiseurs, 106 routes qui
répondent encore 501 (`PasEncore`), modules purs `moteur/` et `saisie/`, services, client `tachesApi.js`,
composants `features/taches/ui/`, coquille, pages vides, jetons `--tch-*`. La fusion 2 leur donne leur contenu réel.

## 0. Ton dossier de travail (à respecter absolument)

Tu tournes dans un worktree git ISOLÉ, à toi seul : c'est le dossier courant de ta session
(`git rev-parse --show-toplevel` te le donne ; note-le, c'est « ton dossier »).
- Tous les chemins que tu passes à Read / Edit / Write / Grep / Glob sont ABSOLUS et SOUS ton dossier. Si une
  commande change de dossier, reviens-y par un `cd` absolu.
- N'écris JAMAIS dans un autre worktree (surtout pas `…\worktrees\erp-task-manager-ai-f8db1b`, `…\dev-taches`,
  `…\dev-taches-f2`, ni `C:\dev\taqinor-os` lui-même) : une garde le refuse, et la contourner par Bash est interdit.
  Lire ce brief hors de ton dossier est la seule exception.
- Base : `git fetch origin dev-taches-f2` puis `git checkout -B <ta branche> origin/dev-taches-f2`. Vérifie que
  `backend/django_core/apps/taches/urls.py` et `frontend/src/api/tachesApi.js` existent et que
  `git merge-base --is-ancestor 92379f6f7 HEAD` réussit ; sinon arrête-toi et dis-le.
- Avant CHAQUE commit : `git branch --show-current` rend ta branche, et `git rev-parse --show-toplevel` rend ton dossier.

## 1. Lire avant d'écrire

- `docs/taches/conception/consignes-construction.md` EN ENTIER (commandes hôte, jonction node_modules sur Windows,
  15 fautes qui font rougir la CI, comment rendre le travail).
- L'en-tête de `docs/plans/PLAN_TACHES.md` puis le texte EXACT de chacune de tes tâches
  (`grep -n "TCH<n> —" docs/plans/PLAN_TACHES.md`) : Preuve, Source, Files, « Nouveau fichier car », maquettes citées.
- Les sections de `docs/taches/reference/{donnees,api,regles,textes}.md` que la tâche cite. LA RÉFÉRENCE FAIT FOI :
  noms de champs, formes JSON, règles, libellés au caractère près (tutoiement).
- `backend/django_core/apps/taches/contract_samples/*.json` = le contrat exact entre serveur et front. Le serveur rend
  exactement ces clés ; un écran et ses tests s'appuient sur ces clés, jamais sur des clés devinées.
- Pour l'APPARENCE d'un écran, les maquettes font foi : `docs/taches/maquettes/<nom>.html` + `taches.css` +
  `SCENARIO.md` (jeu d'exemple chiffré, à reprendre tel quel dans les tests). Les styles réels sont déjà portés dans
  `frontend/src/styles/taches/` : réutilise ces classes sous `.tch`, n'écris pas une seconde feuille.
- Le socle que tu appelles : `selectors/base.py`, `selectors/liens.py`, `serializers/formes.py`, `services/*.py`,
  `moteur/*.py`, `saisie/*.py`, `views/base.py`, `tests/fabriques.py` ; côté front `tachesApi.js`,
  `features/taches/ui/*`, `features/taches/lib/*`, `CoquilleTaches`, `module.config.jsx`.
  Réutilise ; ne recopie aucune règle déjà écrite dans un module pur.

## 2. Construire, tâche par tâche

Test d'abord, dans le module de test que la tâche nomme ; puis le code. Une route construite ne lève plus `PasEncore`.

Backend, sur l'hôte (PowerShell, depuis `<ton dossier>\backend\django_core`) :
`$env:PYTHONPATH='C:\dev\wpstub'; $env:PYTHONIOENCODING='utf-8'; & "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" manage.py check`
- Les tests SANS base tournent (`manage.py test <module>` pour un `SimpleTestCase`, `python -m unittest` pour un module pur).
- Les tests AVEC base ne tournent PAS sur l'hôte (la CI les joue) : écris-les avec un soin particulier, relis chaque
  appel de fabrique contre `tests/fabriques.py` et chaque nom de champ contre le modèle. Dans un `TestCase`, ne nomme
  jamais un attribut de classe `client`. Aucune horloge vivante : date et heure injectées.
- `flake8` + `py_compile` sur tes fichiers. Modèle touché : `makemigrations --check --dry-run` ; une migration
  nouvelle est additive, numérotée à la suite, nommée.

Front, sur l'hôte, depuis `<ton dossier>\frontend` (jonction node_modules : consignes §2) :
- `npx eslint <tes fichiers>` ; `npm run test:unit -- <tes fichiers de test> --testTimeout=30000`. Jamais la suite
  entière, jamais `npx vitest` nu ; aucun vitest laissé en arrière-plan à la fin.
- Un test rend le composant avec le client mocké sur les `contract_samples` et vérifie le COMPORTEMENT ; jamais une
  regex sur le source.

Règles de maison
- Toute donnée est filtrée par société ET propriétaire via les sélecteurs existants (`taches_de(user)`, etc.).
  `company` et propriétaire ne sont jamais lus du corps de requête.
- Confidentialité (`reference/regles.md` §8) : une forme servie à l'assistant ne porte jamais le contenu d'un objet
  confidentiel ; un texte collé ou dicté est une DONNÉE, jamais une consigne.
- Aucun import de `models`/`views` d'une autre app métier : lecture par le `selectors.py` de l'app cible, écriture
  par son `services.py` (fonction mince ajoutée là-bas et testée là-bas si elle manque).
- Aucun chiffre ni libellé inventé : un constat affiché est calculé des données ou omis.
- Aucun `except`/`catch` nu ou vide, aucun `skipTest`, aucune dépendance nouvelle.
- Front : couleurs par jetons seulement (aucun hex, aucun z-index en dur), `:hover` sous `@media (hover: hover)`,
  pas de `position: fixed` hors des motifs déjà permis, tout sous `.tch` ; une erreur s'affiche sous le champ
  fautif ; une liste ne se vide jamais sur un rafraîchissement en échec et un geste (cocher, reporter) ne relit
  jamais toute la liste (mise à jour optimiste, réconciliation, « Annuler ») ; aucun raccourci clavier destructif ;
  cibles tactiles ≥ 44 px ; les paramètres de requête passent par valeur dans `tachesApi.js`.

Interdits
- Modifier `docs/plans/PLAN_TACHES.md`, `docs/CODEMAP.md`, `docs/openapi-schema.yml`, `docs/api-contracts.md`,
  `docs/taches/reference/*` (l'orchestrateur le fait).
- `git push`, `--amend`, `git stash`, rebase ; docker ; lancer une suite entière.
- Toucher un fichier hors des `Files:` de tes tâches, sauf nécessité que tu expliques dans ton rapport. Fichiers
  partagés (`urls.py`, `module.config.jsx`, `index.css`, `tachesApi.js`, `tests/fabriques.py`) : AJOUTS seulement,
  jamais de réécriture ni de réordonnancement.

Un vrai blocage sur une tâche : ne la bâcle pas ; écris pourquoi dans ton rapport et passe à la suivante.

UN commit par tâche, message « TCH<n> — <ce que ça fait> », terminé par la ligne
`Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## 3. Rapport final (court)

La branche, le SHA de tête, puis par tâche : SHA, fichiers, commande de vérification jouée et son résultat
(nombre de tests, flake8, eslint), ce qui n'a PAS pu être vérifié sur l'hôte, tout écart constaté entre la
référence, la maquette et le socle (ne le corrige pas en silence).
