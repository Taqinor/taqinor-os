# Brief commun des lanes de construction — module Calepinage, tour 2 (go-deep L5, 23/11/2026)

« Before reporting progress, audit each claim against a tool result from this session. Only report work you can point
to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output. »

Régime : MIXTE — le module existe. Corrige ou construis sans toucher au reste ; ne suppose jamais qu'une chose
manque : cherche-la d'abord (`docs/CODEMAP.md` §3-§4, puis un grep ciblé). Toute écriture d'écran suit le langage
visuel `docs/audits/l5-calepinage/maquettes-v2/LANGAGE.md` et, quand elle existe, la maquette v2 de l'écran
(`docs/audits/l5-calepinage/maquettes-v2/<Écran>.dc.html`).

## 0. Ton dossier (à respecter absolument)

- Worktree ISOLÉ, à toi seul (`git rev-parse --show-toplevel`). Chemins ABSOLUS et SOUS ton dossier pour Read / Edit /
  Write / Grep / Glob. Lectures permises au dehors : ce brief, les notes de `docs/audits/l5-calepinage/` de la branche
  d'intégration, les fichiers nommés par ton message. Seule écriture permise au dehors : TON fichier d'événements
  (chemin absolu donné dans ton message). N'écris JAMAIS dans un autre worktree, même par Bash.
- Base : `git fetch origin --quiet && git checkout -q -B <ta branche> origin/claude/calpinage-module-l5-aadbde` — la
  branche d'INTÉGRATION de la campagne, jamais `origin/main` (une lane partie de `main` reconstruit du travail déjà
  plié). Vérifie `git log --oneline -1` : le commit de tête est celui de la branche d'intégration.
- Avant CHAQUE commit : `git branch --show-current` et `git rev-parse --show-toplevel` rendent les tiens.
- Front : `frontend\node_modules` n'existe pas dans ton worktree. Crée une JONCTION vers le dossier partagé à jour :
  `cmd /c mklink /J "<ton worktree>\frontend\node_modules" "C:\dev\taqinor-os\.claude\worktrees\l5cal-instr\frontend\node_modules"`.
  N'y installe rien ; ne la retire que par `cmd /c rmdir "<ton worktree>\frontend\node_modules"` (jamais `rm -rf` : il
  viderait le dossier partagé) — et retire-la AVANT ton dernier message.
- Moteur de dessin (`apps/web/src/scripts/roofPro11/`) : même principe, jonction
  `cmd /c mklink /J "<ton worktree>\apps\web\node_modules" "C:\dev\taqinor-os\.claude\worktrees\l5cal-instr\apps\web\node_modules"`,
  tests par `npx vitest run <fichier de test>` depuis `apps/web/`, retirée de la même façon avant ton dernier message.
- Ton fichier d'événements est dans le dossier temporaire de la session (chemin absolu dans ton message), pas dans le
  dépôt : l'orchestrateur le recopie au registre.

## 1. Lire avant d'écrire

Pour chaque tâche : son texte COMPLET (`grep -n "<ID> —" docs/plans/PLAN_AUDIT_*.md` — une tâche est une longue ligne
à 14 clauses : Constat, Given/When/Then, Écran, Persistance, Emplacement, Simplicité, Code net, Appelants, Assertions
existantes, Jumeaux, Listes figées, Contrat partagé, Test rouge d'abord, Preuve en direct, Hors périmètre, Files). Ses
clauses CALCULÉES : `python scripts/audit_tache.py <ID>` — lis sa sortie et colle l'essentiel (appelants, assertions
existantes, jumeaux) dans le message du commit. Chaque fichier touché EN ENTIER et ses appelants (grep du symbole côté
front et serveur).

## 2. Construire, une tâche à la fois, dans l'ordre donné

1. **Le test qui prouve, rouge d'abord** (clause « Test rouge d'abord » de la tâche), dans le module de test EXISTANT
   du fichier touché — jamais un fichier `test_<id>_*.py` par tâche, sauf si la tâche dit « Nouveau fichier car : ».
2. Corrige à la RACINE, partout où le défaut peut exister (clause « Jumeaux » : autre vue, autre thème, autre taille
   d'écran, autre marché).
3. Tes contrôles, et SEULEMENT eux :
   - Python : `python -m flake8 <tes fichiers>` et `python -m py_compile <tes fichiers>` ;
   - LE test que tu répares ou écris, côté serveur :
     `bash "C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/l5cal/tester.sh" "<ton worktree en C:/…>" <nom court de ta lane, lettres et chiffres> <labels de tests…>`
     (conteneur jetable, base de test à toi, ≈ 3 min par appel, UN appel à la fois, jamais `timeout` devant) ;
   - front : `npx eslint <tes fichiers>` et LE test : `npx vitest run --pool=threads --maxWorkers=1 <fichier de test>`
     depuis `frontend/` ;
   - si ta tâche édite un plan ou une garde : la garde citée par la tâche (`python scripts/check_….py`).
   Pas de `docker compose`, pas d'autre conteneur, pas de suite voisine, pas de build du front, pas de Playwright.
   Une migration nécessaire : additive, écrite à la main à la suite de la dernière de l'app sur TA branche, dite dans
   ton rapport (l'orchestrateur vérifie `makemigrations --check` en CI).
4. UN commit par tâche : « <ID> — <ce que ça change pour l'utilisateur> », dernière ligne
   `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
5. Tu ne coches RIEN au plan et tu n'édites ni `docs/plans/*`, ni `docs/CODEMAP.md`, ni le schéma OpenAPI : ce sont
   les fichiers de l'orchestrateur. Dis dans ton rapport ce qui devra être régénéré (schéma OpenAPI, échantillon de
   contrat, golden).

## 3. Trois sorties possibles par tâche — jamais un « réglé » silencieux

Une ligne JSON par tâche dans ton fichier d'événements :
`{"id":"<ID>","tour":2,"etape":"correction","verdict":"corrige|conteste|impossible","commit":"<sha>","test":"<chemin::nom>","gestes_apres":"<gestes exacts pour revoir le résultat à l'écran>","raison":"<obligatoire hors corrige>"}`
- **corrige** : test vert ; `gestes_apres` = la « Preuve en direct » de la tâche, telle qu'on pourra la rejouer.
- **conteste** : la tâche est sans objet ou déjà faite — la preuve (`fichier::symbole`, sortie de commande).
- **impossible** : pas sans affaiblir un test, une règle ou une autre lane — pourquoi, et le plus petit changement
  qui débloquerait.
Besoin d'un changement dans un fichier hors de ta lane : une ligne
`{"id":"<ID>","tour":2,"etape":"demande-croisee","verdict":"ouverte","de":"<ta lane>","vers":"<lane ou couture>","fichier":"…","changement":"…"}`,
jamais l'édition.

## 4. Fautes qui ont rougi la CI des runs précédents — ne les refais pas

Lis `C:/Users/kasri/.claude/projects/C--dev-taqinor-os/memory/plan-drain-ci-bug-classes.md` (25 lignes utiles). Les
plus fréquentes sur ce module :
1. Un test ne lit jamais le source par expression régulière : il EXÉCUTE le code.
2. Un mock d'une route qui a un `contract_samples/*.json` importe `exempleContrat` / `reponseContrat`, jamais une
   réponse tapée à la main ; une clé ajoutée à un contrat et la clé servie arrivent dans le MÊME commit.
3. Nouveau `SerializerMethodField` → `@extend_schema_field` ; nouveau paramètre de requête → déclaré sur la vue.
4. Spec ou test : ni `setTimeout(`, ni `page.waitForTimeout(`, ni `time.sleep(` — on attend une condition.
5. Un texte changé est cité ailleurs : `grep -rn "<phrase>" backend frontend/src frontend/e2e` et mets tout à jour
   dans le même commit ; une clé ajoutée à une réponse casse les goldens « appelants inchangés ».
6. Toute route nouvelle répond 404 à une autre société AVANT de lire le corps (`test_isolation_societe`).
7. CSS du module : jetons seulement (aucune couleur en dur hors des fichiers de jetons, aucun `z-index` en dur),
   `:hover` sous `@media (hover: hover)`, aucune classe héritée du site public.
8. Un fichier de 2 000 lignes ou plus ne grossit pas : extrais dans un fichier voisin (clause « Code net »).
9. Un `catch {}` vide est refusé : rends une valeur ou affiche l'erreur.
10. Le prix d'achat (`prix_achat`) n'apparaît dans aucune réponse lue par un écran client ni aucun document.

Fautes de la vague 1 de CETTE campagne (chacune a rougi la CI une fois) :
11. Une fonction publique d'un `services/*.py` sans appelant hors de son fichier est refusée
    (`scripts/check_services_appeles.py`) : préfixe-la d'un `_` si elle ne sert que dans son fichier.
12. Tout nouveau repère `data-testid="cal-…"` est déclaré dans le MÊME commit dans
    `frontend/src/features/calepinage/E2E_HOOKS.md` et dans `ALL_HOOKS` de `e2eHooks.test.mjs`.
13. Pas de nouveau fichier de test par tâche, y compris sous `apps/web` (`scripts/check_test_placement.py`) : le test
    va dans le fichier de test existant du module (ex. `zones.test.ts`).
14. Dans le moteur de dessin, `serializeLayout` rend TOUJOURS le document courant, même pendant un geste : trois tests
    d'`apps/web` le gardent. Après toute retouche d'un geste ou de la sérialisation, joue les tests du dossier
    `roofPro11` que ton fichier touche.
15. Une clé ajoutée à une réponse de l'API, ou un champ de modèle : dis-le dans ton rapport — l'orchestrateur
    régénère `docs/api-contracts.md` et `docs/openapi-schema.yml` au pli ; un `on_delete` ajouté ou déplacé change
    `docs/on-delete-financial-audit.md` (dis-le aussi).

## 5. Interdits

Fichiers hors de ta lane ; fichiers de l'orchestrateur ; `git push`, `--amend`, `git stash`, rebase ; `docker compose` ;
suite entière ; build + Playwright ; toute commande vers la prod ; tout changement d'un chiffre que voit un client sans
que ta tâche le nomme (arrête-toi et dis-le).

## 6. Rapport final (15 lignes au plus)

Branche + SHA de tête ; par tâche : sortie (corrige / conteste / impossible), SHA, test (rouge → vert, commande et
résultat) ; ce qui n'a PAS été vérifié ; ce que l'orchestrateur doit régénérer ; demandes croisées ouvertes ; tout
défaut voisin vu en passant (une ligne chacun).
