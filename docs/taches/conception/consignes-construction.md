# Consignes de construction — app `taches`

Source entre parenthèses (mémoire = `memory/`). « À vérifier » = commande non attestée.

## 1. Avant d'écrire

- Lis : `docs/plans/PLAN_TACHES.md` (ta tâche, `Files:`, `@after`), `docs/taches/reference/*.md` (font foi), les maquettes citées. (consignes.md)
- Vérifie sur le fichier réel que la tâche n'est pas déjà faite, pas sur un rapport. (worktree_git_mechanics)
- Premier geste : `git log --oneline main..HEAD` vide et HEAD plus vieux que `main` → `git reset --hard main`. Lane de seconde vague : `git fetch && git checkout -B <x> origin/<intégration>`, puis le marqueur du prompt. (worktree_git_mechanics)
- JAMAIS : fichiers d'une autre lane ; `docs/PLAN*.md`, `docs/CODEMAP.md`, DONE LOG, `docs/api-contracts.md`, `docs/openapi-schema.yml` (l'orchestrateur) ; fichier d'un autre propriétaire non nommé par ta tâche. Fichier partagé nommé : ajout en fin seulement. (verif-squelette M3, brief-r1)
- Un commit par tâche, aussitôt finie, qui tient seul. Message = identifiant + libellé. Jamais `--amend`, jamais de push, jamais de `git stash`. (worktree_git_mechanics)
- Pas de primitive maison : numérotation `core.numbering`, historique `records`, pièces `records.Attachment`. (brief-r1 §3)
- Write refuse parfois un nouveau fichier : écris-le dans le scratchpad et dis-le, sans contournement Bash. (worktree_windows_tooling)

## 2. Le worktree sur Windows

- Pas de `node_modules`. Jonction (PowerShell) :
  `New-Item -ItemType Junction -Path <wt>\frontend\node_modules -Target C:\dev\taqinor-os\frontend\node_modules`
  Vérifie la cible (`ls …\node_modules\vitest`). Pas `mklink` (lettre doublée). (worktree_windows_tooling)
- Ne la commite jamais. Ne lance jamais `npm ci`/`install` dedans. Jamais `rm -rf` ni `git worktree remove` dessus (vide la cible).
- Retrait du lien seul : `cmd /c rmdir <wt>\frontend\node_modules` ou `(Get-Item node_modules).Delete()`.
- Depuis `frontend/` : `npx eslint <tes fichiers>` ; `npm run test:unit -- <tes fichiers> --testTimeout=30000`. Jamais `npx vitest` nu, jamais la suite entière. Node : `C:\Program Files\nodejs`, hors PATH.
- Les goldens `*.golden.test.jsx` mentent via la jonction : signale-les, ne les écarte pas comme « préexistants ». (worktree_windows_tooling 15/11)
- Python : `$env:LOCALAPPDATA\Programs\Python\Python313\python.exe` (Django 5.1 : vérifié ici) ; 3.11 : `flake8` seulement.
- Pièges : heredoc > ~5 Ko ou avec apostrophes tronqué, `\` mangés → outil Write/Edit. Chemins `/c/...` donnés à Python/Node visent un autre fichier (`cygpath -w`). PowerShell 5.1 : pas de `&&`. Jamais `Get-Content | Set-Content` sur de l'UTF-8. Commit : `git commit -F -` depuis Bash. (worktree_windows_tooling)
- CRLF : écris en LF. Un test qui cherche `\n` dans une source échoue en local et passe en CI. (worktree_windows_tooling)
- Ne touche pas `package-lock.json` ; si npm l'a changé : `git checkout -- frontend/package-lock.json`. (frontend_lock_crossplatform)

## 3. Sur l'hôte, et ce qui n'y tourne pas

Règle du fondateur : la CI vérifie d'abord ; jamais docker local, jamais la base de test locale, jamais `test-backend.ps1`. (docker_local_testdb_do_not_fight ; CLAUDE.md étape 5)

- `python -m py_compile` et `flake8 --max-line-length=120` sur tes fichiers. (La CI : `flake8 backend --max-line-length=120 --exclude=migrations,parked` ; une sélection réduite a laissé passer E302/W391.) (host_gates_before_push)
- Tests purs : module sans import Django, test en `unittest.TestCase` (ou `SimpleTestCase`), nom `test_*.py`, sans base, sans horloge vivante. `python -m unittest <module>` sur l'hôte ; le lanceur Django de la CI le découvre pareil. `manage.py test <module>` marche sans base pour un `SimpleTestCase` (Python 3.13, `PYTHONPATH=C:\dev\wpstub`). (worktree_windows_tooling)
- Avant de créer un dossier `tests/`, vérifie qu'il n'y a pas déjà `tests.py` (le paquet le masque). (catalogue #103)
- Gardes `scripts/` (celles de diff avec `--base origin/main`, APRÈS ton commit) :

| Garde | Attrape |
|---|---|
| `check_on_delete` | `CASCADE` sans `# on_delete:` |
| `check_unique_scoping`, `check_company_fk`, `check_fk_scoping` | unicité sans `company` |
| `check_get_or_create`, `check_read_modify_write` | clé sans contrainte ; compteur non verrouillé |
| `check_naive_datetime`, `check_except_larges` | `datetime.now()`, `except` muet |
| `check_tenant_isolation`, `check_viewset_model_scope` | vue sans filtre de société |
| `check_safe_migrations`, `check_migration_safety`, `check_choices_declares` | DDL dangereux |
| `check_forme_code`, `check_test_placement`, `check_test_tags` | fonction > 60 lignes ; fichier de test neuf ; test lourd sans `@tag` |
| `check_services_appeles`, `check_ecrans_atteignables`, `check_taches_cablage`, `check_api_contract`, `check_frontend_query_params`, `check_api_shapes`, `check_ownership` | service sans appelant, écran inatteignable, appel sans route, paramètre non déclaré, contrat |
| `frontend/scripts/check_hex.mjs`, `check_frontend_errors.py` | couleur en dur ; `JSON.stringify(err)` |
| `lint-imports` (dans `backend/django_core`) | frontières d'apps |

- Les deux suites de la CI, sans docker : `python scripts/ci_guards.py stage-names` et `… backend-lint-fast`. (host_gates_before_push 17/11)
- Ne tourne PAS ici : tests à base, e2e Playwright, mesures de navigateur, schéma OpenAPI sans cale (§7).
- Lis la sortie d'une vérification AVANT le commit, dans sa propre commande. Jamais `cmd | grep && commit`. (host_gates_before_push)

## 4. Les 15 fautes qui font rougir la CI

1. **`CASCADE` sans commentaire** : `# on_delete: <raison>` sur la ligne. (brief-r1)
2. **Unicité sans `company`/`is_deleted`** : `company` dans toute contrainte ; partielle si suppression douce. (check_unique_scoping)
3. **Noms d'index** : ≤ 30 car., identiques dans `Meta` et migration, `name=` explicite. (catalogue #13, migration_index_name_divergence)
4. **`get_or_create`** : clé couverte par une `UniqueConstraint`. `next_reference()` : `field=` si le champ n'est pas `reference`, dans `transaction.atomic()`. (#62)
5. **Compteur lu-modifié-écrit** : `select_for_update()` ou `F()`. (check_read_modify_write)
6. **Fonction > 60 lignes logiques** : découpe avant le commit. (check_forme_code)
7. **Vue sans schéma OpenAPI** : `APIView` + `@extend_schema(request, responses)`, `<int:id>` typés ; ni `@api_view` nu ni `OpenApiTypes.OBJECT`. ViewSet : `ordering_fields`, `search_fields`. (verif-squelette B3, #98, #140)
8. **Paramètre de requête non déclaré** par l'opération OpenAPI que le front frappe. (check_frontend_query_params)
9. **Test lourd sans `@tag('slow'|'pdf')`**. (check_test_tags)
10. **Faux second locataire** : un `make_company()` en `get_or_create(slug=…)` rend la même société. Deux slugs distincts, `pk` différents. (plan_drain_ci_bug_classes, 31/07)
11. **Test nommé d'après une tâche / fichier neuf** : ajoute au module existant ; fichier neuf seulement avec « Nouveau fichier car : » cité en backticks sur la tâche cochée. (check_test_placement, #40)
12. **Écran inatteignable** : tout `.jsx` non test de `features/taches` est monté par une route ou la coquille. (verif-squelette B1)
13. **Chemin d'API sans route** ; échantillon de contrat sans enveloppe `{endpoint, exemple, pourquoi}`. (check_api_contract, B2)
14. **Couleur en dur, dépendance npm, `JSON.stringify(err)` affiché** : `var(--token)`, aucune dépendance sans accord, message du champ fautif. (check_hex, brief-r1)
15. **Hooks e2e et `Toaster`** : classes `ap-*`, `att-*`, `pp-*` conservées ; titre de page jamais `role=heading` ; un seul `<Toaster>`. (ui_redesign_e2e_contract)

Aussi : `max_length` ≥ tout littéral écrit (#1) ; `BooleanField` omis en multipart = `False` (#15) ; `list()` dans un décorateur de ViewSet = `TypeError` à l'import (#150).

## 5. Migration

- Contre l'énoncé de la mission : `makemigrations --check --dry-run` TOURNE sur l'hôte (exécuté ici : « No changes detected »). Depuis `backend/django_core` :
  `$env:PYTHONPATH='C:\dev\wpstub'; $env:PYTHONIOENCODING='utf-8'; & "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" manage.py makemigrations --check --dry-run`
  L'alerte « failed to resolve host db » est normale. (worktree_windows_tooling, catalogue #49)
- Donc aucun conteneur (la mémoire tolérait un conteneur jetable de 2 min, mais la règle du 27/10 l'interdit comme gate).
- Génération : même commande avec `makemigrations taches` (sans base). Non rejouée sur une app neuve : à vérifier. En cas d'échec, écris à la main et dis-le.
- À la main : `CreateModel` dans l'ordre des FK ; `dependencies` = `swappable_dependency(settings.AUTH_USER_MODEL)`, `('authentication', <dernière réelle>)`, `contenttypes` et `records` si FK vers eux.
- `Meta` et migration : mêmes noms d'index et de contraintes ; `Q(a=1,b=2)` y est trié alphabétiquement ; `CheckConstraint(condition=…)` (Django 5.1) déclarée dans `Meta.constraints`. (#2)
- Relance `--check` après chaque intégration de `main` (deux feuilles = rouge). Renumérotation au pli seulement. Migrations prévues : `taches` 0001 (TCH9), 0002 (TCH121), `notifications` 0079 (TCH20). (plan-squelette §6)

## 6. Rendre son travail

Une ligne par tâche : `<ID> | <SHA> | <fichiers> | <garde lancée → sortie résumée> | non vérifié : <…>`

- « Non vérifié » = tests à base, e2e, OpenAPI, goldens, navigateur. Écris-le même si tout est vert.
- Bloquée : `[BLOCKED: raison]` après l'identifiant, tâche suivante. Une tâche `@acceptation` n'est jamais jouée par une lane. (CLAUDE.md 3-bis)
- Termine par `git status` et `git log --oneline` : l'orchestrateur ne croit pas le message final. (worktree_git_mechanics)

Bloc de preuve :

> Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## 7. Pour l'orchestrateur

- **Pli** : `git merge --no-ff` lane par lane après `git show <sha> --stat`. Conflit > ~100 lignes : lâcher et remettre en file sur la base pliée. Coche seulement si `git diff --stat` montre les `Files:`. (worktree_git_mechanics)
- **Après le dernier pli et le commit de ticks** : `makemigrations --check`, les deux suites `ci_guards.py`, puis `$env:PYTHONIOENCODING='utf-8'; python -X utf8 scripts/codemap_fingerprint.py --write` et `--check`. Tout fichier ajouté sous `features/` ou `pages/` (même un test) déplace l'empreinte. (codemap_fingerprint)
- **OpenAPI** : cale de réglages hors dépôt (`from erp_agentique.settings.dev import *`, `SCHEMA_PATH_PREFIX='/api'`), `DJANGO_SETTINGS_MODULE=<cale>`, `python scripts/check_openapi_schema.py --write` (30/09, hôte, sans docker ; non rejoué ici : à vérifier). Sinon la CI imprime les lignes à insérer : un cycle. Diff hors `taches` = génération fausse. (host_gates_before_push)
- **PR** : aucune tant qu'un changement reste ouvert ; puis `gh pr create` et `mcp__ccd_pr__set_monitor auto_fix:true` dans le même tour, sans demander. Attente : `powershell -File scripts/watch-ci.ps1 -Pr <n>` en fond. Fusion : `gh pr merge --auto --merge`. Un rouge à N problèmes : un fixer par groupe de fichiers disjoints. (own_the_ci_loop)
- **Réservations** : `python scripts/plan_claims.py renew <clés> --owner <hôte>/<branche>` à chaque réveil ; `release` après la fusion seulement ; une clé = un push git (15-30 s). (plan_claims.py)
- **Machine** : 4 cœurs, 34 Go ; 8 lanes saturent le processeur. Vise 4 lanes d'écriture, 8 au plus ; ~1 Go de disque par worktree ; ni création ni suppression de worktree pendant une vague ; casse les jonctions avant tout retrait. (machine_laptop_capacite)
- **Ce qui a tué des nuits** : Windows Update (11/11) ; plafond d'usage de 5 h (27/10, surveiller `get_usage`) ; lane qui attend une notification et ne se réveille jamais (la relancer par `SendMessage`) ; `find .` depuis la racine ; dispatch pendant une opération git ; `TaskOutput` bloquant. (plan_run_addenda)
- **Avant la fusion** : acceptations 3-bis sur pile locale, parcours client lu de bout en bout. (CLAUDE.md, lecons-construction-qjr5 §8)
