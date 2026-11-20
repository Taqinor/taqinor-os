# Sonde de régime — NEUF / EXISTANT / MIXTE (avant tout niveau de go-deep)

But : décider en moins de cinq minutes si l'on construit du neuf ou si l'on améliore l'existant, sur `origin/main`,
et l'annoncer en une ligne. Le régime fixe l'ORDRE des étapes et les PREUVES ; le niveau fixe le volume.

## 1. Lire `origin/main`, jamais le dossier de travail
```sh
export MSYS_NO_PATHCONV=1            # Git Bash sous Windows : sinon « origin/main:chemin » est réécrit en chemin Windows
git fetch origin main --quiet
SHA=$(git rev-parse --short=9 origin/main)
```
Piège mesuré : un worktree périmé n'avait pas `apps/taches` alors que `origin/main` en avait 344 fichiers ; même
`python scripts/check_ownership.py --owner-of …` lu dans ce worktree répondait « AUCUN » (il lit le `ownership.yml`
du dossier) : toujours `git show origin/main:<fichier>`.

## 2. Les signaux (`m` = nom du module ou du mot de la demande)
```sh
T=$(git ls-tree -r --name-only origin/main)
F=$(printf '%s\n' "$T" | grep -cE "^(backend/django_core/apps/$m/|frontend/src/(features|pages)/$m/)")      # FORT
TT=$(printf '%s\n' "$T" | grep -E "^(backend/django_core/apps/$m/|frontend/src/(features|pages)/$m/)" | grep -cE "test|spec")
E2E=$(git ls-tree -r --name-only origin/main frontend/e2e | grep -ci "$m")
PLAN=$(git ls-tree --name-only origin/main docs/plans/ | grep -i "$m" | head -1)                                   # FORT si cases [x]
[ -n "$PLAN" ] && X=$(git show origin/main:$PLAN | grep -cE '^\s*- \[x\]') && O=$(git show origin/main:$PLAN | grep -cE '^\s*- \[ \]')
OWN=$(git show origin/main:docs/ownership.yml | grep -c "apps/$m/")
MAP=$(git show origin/main:docs/CODEMAP.md | grep -ciw "$m")                                                         # indice seulement
URLS=$(git ls-tree -r --name-only origin/main backend/django_core/apps/$m | grep -c 'urls.py')
PARQ=$(git show origin/main:backend/django_core/core/parked.py | grep -c "'$m'")
MERGES=$(git log --first-parent --oneline origin/main -- backend/django_core/apps/$m frontend/src/features/$m frontend/src/pages/$m | wc -l)
```
Mesuré le 20/11/2026 sur `origin/main` 6623b6ea3 :

| m | F | TT | E2E | plan, cochées / ouvertes | OWN | MAP | URLS | PARQ | MERGES |
|---|---|---|---|---|---|---|---|---|---|
| taches | 344 | 92 | 10 | PLAN_TACHES 200 / 0 | 1 | 5 | 1 | 0 | 6 |
| calepinage | 1 070 | 606 | 4 | PLAN_AUDIT_CALEPINAGE | 3 | 63 | 2 | 0 | — |
| copilote | 0 | 0 | 0 | aucun | 0 | 11 | — | — | — |
| cpq | — | — | — | — | — | — | 0 | 1 (parqué) | — |
| zzznouveau | 0 | 0 | 0 | aucun | 0 | 0 | — | — | — |

Les verbes de la demande sont des INDICES : « construis / crée / ajoute / je veux un… » penchent NEUF ; « améliore /
revois / corrige / refais / polis / look at what was done / redo » penchent EXISTANT. Ils ne décident jamais seuls.

## 3. La décision : les promesses servies
1. Écrire les promesses de la demande, une phrase chacune (5 à 15), dans le fichier d'état.
2. Pour chacune, une preuve sur `origin/main` : la route, l'écran, l'action ou le test qui la sert (chercher par
   CODEMAP §4 au MOT, puis `git ls-tree` / `git grep -n <motif> origin/main -- <chemins>`), sinon « absente » ; « partielle » si
   le geste existe mais pas le cas demandé.
3. P = (servies + ½ partielles) / total.
   - **NEUF** : P < 20 % ET au moins 2 signaux FORTS absents (F = 0, plan absent ou 0 cochée).
   - **EXISTANT** : P > 80 %.
   - **MIXTE** : entre les deux, OU capacité neuve dont l'hôte existe (une app + un fichier-patron qui fait déjà la
     même chose ailleurs).
   Seuils = valeurs de départ sans calibrage (aucune source ne fournit de détecteur) : noter P, les signaux et le
   verdict dans le fichier d'état ; la rétro de chaque run dit si le régime annoncé a tenu.

## 4. L'annonce (une ligne, puis on avance — jamais une question)
« Régime : EXISTANT · L4 · origin/main@<SHA> — <F> fichiers, <TT> tests, plan <X>/<X+O> cochées, promesses servies
<s>/<t>. Dis « neuf / mixte / existant » pour imposer. »
NEUF : « Régime : NEUF · L4 · origin/main@<SHA> — aucun module trouvé (0 fichier, 0 plan, 0 propriétaire), promesses
servies 0/<t>. » La parole de Reda l'emporte. Bascule en cours de route, en une ligne, dès que le tour 0 ou R1
contredit (module trouvé ailleurs, API absente) ; la bascule est notée dans le fichier d'état.

## 5. Quand la règle se trompe, et la parade
| Cas | Signal | Classement |
|---|---|---|
| Nom ≠ dossier (« copilote » : 11 mentions CODEMAP, 0 fichier sous ce nom, code dans `agent`, `crm`, `fastapi_ia`) | F = 0 mais MAP > 0 | décider par les promesses, pas par F ; souvent MIXTE |
| Coquille parquée (dossier sans routes ni tests, listé dans `core/parked.py`) | PARQ = 1, URLS = 0 | NEUF, avec l'archive comme référence (`docs/parked-modules.md` : recette de restauration) |
| Plan écrit, rien construit | plan présent, X = 0 | NEUF |
| Code éteint par un interrupteur ou un droit | F > 0, activation absente | EXISTANT sans utilisateurs (pas de données, risque de régression moindre) |
| « Refais » au sens d'une refonte | P > 80 % mais la demande change le fond | EXISTANT en mode étrangleur : le neuf derrière un interrupteur, l'ancien gardé, bascule écran par écran |
| « Est-ce en ligne ? » | illisible dans le dépôt (merge ≠ déployé) | lire l'activation (droit, interrupteur, `installable`) ; lire la prod = geste à part (accord de lecture prod) |

## 6. Ce que le régime change (rappel de la skill, détail opératoire)
- **NEUF** : références et recherche → conception → maquettes (si écran) → contrat d'abord, SEUL sur `main`
  (PACT10, `contract_samples/`) → lot de décisions (Tensions 3 de la skill) → plan + claims → construction par un
  plan run, module invisible jusqu'à activation → les tours de relecteurs commencent quand le premier écran tourne.
  Preuves : contrat testé des deux côtés, acceptation en direct par fusion, critique du diff, invisibilité.
- **EXISTANT** : état des lieux promesse par promesse (ce qui existe, ce qui a été laissé, décidé seul, jamais
  vérifié) → goldens des chiffres servis sur le commit intact → instrument → tours. Preuves : capture avant / après
  regardée, goldens inchangés, contre-vérification par des neufs qui cherchent d'abord la régression.
- **MIXTE** : état des lieux de la seule surface touchée → contrat de la moitié neuve → lane(s) avec le fichier-patron
  et la liste « à ne pas changer » → couture. Preuves : test rouge d'abord, goldens de la surface touchée inchangés,
  fichiers d'autres propriétaires en AJOUT seulement.
