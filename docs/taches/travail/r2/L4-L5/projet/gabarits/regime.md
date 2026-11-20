# Sonde de régime — NEUF / EXISTANT / MIXTE (avant tout niveau de go-deep)

But : décider en moins de cinq minutes si l'on construit du neuf ou si l'on améliore l'existant, sur `origin/main`,
et l'annoncer en une ligne. Le régime fixe l'ORDRE des étapes et les PREUVES ; le niveau fixe le volume. La règle est
TOTALE : tout cas tombe dans une des trois classes.

## 1. Lire `origin/main`, jamais le dossier de travail
```sh
export MSYS_NO_PATHCONV=1            # Git Bash sous Windows : sinon « origin/main:chemin » est réécrit en chemin Windows
git fetch origin main --quiet
SHA=$(git rev-parse --short=9 origin/main)
```
Piège mesuré : un worktree périmé n'avait pas `apps/taches` alors que `origin/main` en avait 344 fichiers ; même
`python scripts/check_ownership.py --owner-of …` lu dans ce worktree répondait « AUCUN » (il lit le `ownership.yml`
du dossier) : toujours `git show origin/main:<fichier>`.

## 2. Les signaux
`m` = le nom de la demande ; `q` = `m` ET ses synonymes français / anglais, en motif `grep -E` (ex. `widget|tuile`,
`task|tâche|taches`, `go-deep|go deep`). Chercher dans TOUT l'arbre (`.claude/`, `scripts/`, `docs/`, `apps/web/`, le
serveur, le front), pas seulement les dossiers d'app.
```sh
T=$(git ls-tree -r --name-only origin/main)
ALL=$(printf '%s\n' "$T" | grep -v '^docs/' | grep -ciE "$q")                              # FORT : chemins sous ces noms, hors docs/
TXT=$(git grep -ilE "$q" origin/main | wc -l)                                              # indice : fichiers qui en parlent
F=$(printf '%s\n' "$T" | grep -cE "^(backend/django_core/apps/$m/|frontend/src/(features|pages)/$m/)")      # FORT (module d'app)
TT=$(printf '%s\n' "$T" | grep -E "^(backend/django_core/apps/$m/|frontend/src/(features|pages)/$m/)" | grep -cE "test|spec")
E2E=$(git ls-tree -r --name-only origin/main frontend/e2e | grep -ciE "$q")
PLAN=$(git ls-tree --name-only origin/main docs/plans/ | grep -iE "$q" | head -1)                               # FORT si cases [x]
[ -n "$PLAN" ] && X=$(git show origin/main:$PLAN | grep -cE '^\s*- \[x\]') && O=$(git show origin/main:$PLAN | grep -cE '^\s*- \[ \]')
OWN=$(git show origin/main:docs/ownership.yml | grep -c "apps/$m/")
MAP=$(git show origin/main:docs/CODEMAP.md | grep -ciwE "$q")                                                   # indice seulement
URLS=$(git ls-tree -r --name-only origin/main backend/django_core/apps/$m | grep -c 'urls.py')
PARQ=$(git show origin/main:backend/django_core/core/parked.py | grep -c "'$m'")
```
Mesuré le 20/11/2026 sur `origin/main` 6623b6ea3 (signaux de module) :

| m | F | TT | E2E | plan, cochées / ouvertes | OWN | MAP | URLS | PARQ |
|---|---|---|---|---|---|---|---|---|
| taches | 344 | 92 | 10 | PLAN_TACHES 200 / 0 | 1 | 5 | 1 | 0 |
| calepinage | 1 070 | 606 | 4 | PLAN_AUDIT_CALEPINAGE | 3 | 63 | 2 | 0 |
| copilote | 0 | 0 | 0 | aucun | 0 | 11 | — | — |
| cpq | — | — | — | — | — | — | 0 | 1 (parqué) |

Mesuré le 20/11/2026 sur `origin/main` 81899193d (signaux de tout l'arbre) : `widget|tuile` ALL = 33 (dont
`apps/taches/contract_samples/tuile.json`), TXT = 690 ; `go-deep` ALL = 1 (la skill), TXT = 36 ; `copilote` ALL = 5,
TXT = 408 ; `zzznouveau` ALL = 0, TXT = 0. Plans et notes (`docs/`) se lisent par PLAN et TXT, pas par ALL. Exemple de l'erreur évitée : « cant we have our own widget on iphone ? »
donnait NEUF par les seuls dossiers d'app ; l'arbre entier trouve la tuile → MIXTE.

Les verbes de la demande sont des INDICES : « construis / crée / ajoute / je veux un… » penchent NEUF ; « améliore /
revois / corrige / refais / polis / look at what was done / redo » penchent EXISTANT. Ils ne décident jamais seuls.

## 3. La décision : les promesses servies
1. Écrire les promesses de la demande, une phrase chacune (5 à 15), dans le fichier d'état.
   Demande sans promesse propre (« améliore / rends meilleur / polis X ») : les promesses sont celles que X sert
   déjà (son contrat, ses tests, son écran) ; X trouvé → P sur elles → EXISTANT.
2. Pour chacune, une preuve sur `origin/main` : la route, l'écran, l'action, le fichier ou le test qui la sert
   (CODEMAP §4 au mot, puis `git ls-tree` / `git grep -n <motif> origin/main -- <chemins>`), sinon « absente » ;
   « partielle » si le geste existe mais pas le cas demandé.
3. P = (servies + ½ partielles) / total.
   - **NEUF** : P < 20 % ET F = 0 ET aucun hôte parmi les chemins ALL ET aucun plan à son nom avec des cases cochées
     (un plan dont seules des tâches d'échafaudage du dépôt sont cochées compte comme absent). ALL > 0 se LIT, il ne
     se compte pas : un chemin qui fait déjà le même geste sur la même donnée est un hôte (→ MIXTE) ; un homonyme
     n'en est pas un (ex. les `tasks.py` de Celery pour « task »).
   - **EXISTANT** : P > 80 %.
   - **MIXTE** : tout le reste — dont des signaux contradictoires, et une capacité neuve dont l'hôte existe (une app
     + un fichier-patron qui fait déjà la même chose ailleurs).
4. **Demande qui vise un outil ou une méthode** (une skill, un script, un job de CI), pas un produit : même règle sur
   l'artefact visé. Ex. : « fais un L4 / L5 de go-deep » → `.claude/skills/go-deep/SKILL.md` existe → EXISTANT ou
   MIXTE, jamais NEUF ; la preuve y est le rejeu d'un run passé contre le texte, pas une maquette.
5. Seuils 20 % / 80 % = valeurs de départ, non calibrées : à recaler après le premier L4 lancé depuis la skill.
   Noter P, les signaux et le verdict dans le fichier d'état ; la rétro dit si le régime annoncé a tenu.

## 4. L'annonce (une ligne, puis on avance — jamais une question)
« Régime : EXISTANT · L4 · origin/main@<SHA> — <F> fichiers, <TT> tests, plan <X>/<X+O> cochées, promesses servies
<s>/<t>. Dis « neuf / mixte / existant » pour imposer. »
NEUF : « Régime : NEUF · L4 · origin/main@<SHA> — rien trouvé sous <q> (0 chemin, 0 plan, 0 propriétaire), promesses
servies 0/<t>. » La parole de Reda l'emporte. Bascule en cours de route, en une ligne, dès que le tour 0 ou R1
contredit (module trouvé ailleurs, API absente) ; la bascule est notée dans le fichier d'état.

## 5. Cas particuliers (chacun a sa classe)
| Cas | Signal | Classement |
|---|---|---|
| Nom ≠ dossier (« copilote » : 11 mentions CODEMAP, 0 fichier d'app sous ce nom, code dans `agent`, `crm`, `fastapi_ia`) | F = 0 mais ALL > 0 | MIXTE (sauf P > 80 % → EXISTANT) |
| Coquille parquée (dossier sans routes ni tests, listé dans `core/parked.py`) | PARQ = 1, URLS = 0 | NEUF, avec l'archive comme référence (`docs/parked-modules.md` : recette de restauration) |
| Plan écrit, rien construit | plan présent, X = 0, ALL = 0 | NEUF |
| Code éteint par un interrupteur ou un droit | F > 0, activation absente | EXISTANT sans utilisateurs (pas de données, risque de régression moindre) |
| « Refais » au sens d'une refonte | P > 80 % mais la demande change le fond | EXISTANT en mode étrangleur : le neuf derrière un interrupteur, l'ancien gardé, bascule écran par écran |
| « Est-ce en ligne ? » | illisible dans le dépôt (merge ≠ déployé) | lire l'activation (droit, interrupteur, `installable`) ; lire la prod = geste à part (accord de lecture prod) |

## 6. Ce que le régime change (rappel de `L4.md`, détail opératoire)
- **NEUF** : références et recherche → conception → maquettes (si écran) → contrat d'abord, SEUL sur `main`
  (PACT10, `contract_samples/`) → lot de décisions (Tensions 3 de `L4.md`) → plan + claims → construction par un
  plan run, module invisible jusqu'à activation → les tours de relecteurs commencent quand le premier écran tourne.
  Preuves : contrat testé des deux côtés, acceptation en direct, critique du diff, invisibilité.
- **EXISTANT** : état des lieux promesse par promesse (ce qui existe, ce qui a été laissé, décidé seul, jamais
  vérifié) → goldens des chiffres servis sur le commit intact → instrument → tours. Preuves : capture avant / après
  regardée, goldens inchangés, contre-vérification par des neufs qui cherchent d'abord la régression.
- **MIXTE** : état des lieux de la seule surface touchée → contrat de la moitié neuve → lane(s) avec le fichier-patron
  et la liste « à ne pas changer » → couture. Preuves : test rouge d'abord, goldens de la surface touchée inchangés,
  fichiers d'autres propriétaires en AJOUT seulement.
