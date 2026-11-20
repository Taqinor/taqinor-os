# Brief commun des lanes de CORRECTION — <périmètre>, tour <n> (go-deep L4 / L5)

<Bloc d'ancrage de CLAUDE.md, mot pour mot.>

Ta lane : <id>, ses tâches de plan <ids>, ses fichiers (TU NE TOUCHES QUE CEUX-LÀ) : <liste>. Régime : <EXISTANT :
« corrige sans toucher au reste ; ne suppose jamais qu'une chose manque : cherche-la d'abord (grep) » | MIXTE : idem +
« suis le motif de `<fichier-patron>` ; liste à ne pas changer : <…> » | NEUF : « ne construis que les promesses de ta
lane ; le fichier de contrat `<…>` est l'interface »>.

## 0. Ton dossier (à respecter absolument)
- Worktree ISOLÉ, à toi seul (`git rev-parse --show-toplevel`). Chemins ABSOLUS et SOUS ton dossier pour Read / Edit /
  Write / Grep / Glob ; lectures permises au dehors : ce brief, la consolidation, le contrat, les fiches de classes,
  les rapports et captures des relecteurs. Seule écriture permise au dehors : TON fichier d'événements
  `<registre>/evenements/T<n>-lane-<id>.jsonl` (chemin absolu ; format `registre.md`). N'écris JAMAIS dans un autre
  worktree, même par Bash.
- Base : `git fetch origin tests/T<n>-<id>` puis `git checkout -B lane/T<n>-<id> origin/tests/T<n>-<id>` (la branche où
  le rédacteur des tests premiers a posé tes tests ; sans tests premiers : `origin/<branche d'intégration>`) ; vérifie
  `git merge-base --is-ancestor <sha attendu> HEAD`, sinon arrête-toi et dis-le.
- Avant CHAQUE commit : `git branch --show-current` et `git rev-parse --show-toplevel` rendent les tiens.
- Front : `frontend\node_modules` est une JONCTION vers le dossier partagé (`cmd /c mklink /J …` si elle manque) ;
  n'y installe rien ; ne la retire que par `cmd /c rmdir` (jamais `rm -rf` : il viderait le dossier partagé).

## 1. Lire avant d'écrire
Le texte complet de chacune de tes tâches ; le constat d'origine et sa capture ; la fiche d'invariant de chaque classe
que tu touches (sa LISTE d'endroits violables et sa MATRICE de conditions sont ta liste de travail, pas seulement le
symptôme) ; les références du périmètre ; chaque fichier touché EN ENTIER et ses appelants (`grep` du symbole côté
front et serveur).

## 2. Corriger (S1-S2 d'abord)
1. **Le test qui prouve** : pour une classe ou un S1-S2 perte de données / chiffre faux, il t'est DONNÉ (écrit par le
   rédacteur des tests premiers, branche `tests/T<n>-<id>`) et tu ne le modifies pas — le pli refuse ta lane si
   `git diff --name-only origin/tests/T<n>-<id>..HEAD -- <fichiers de test donnés>` n'est pas vide. Sinon : écris-le
   rouge d'abord, dans le module de test EXISTANT du fichier touché.
2. Corrige à la RACINE (pas de pansement, pas de `setTimeout` pour masquer une course, pas de `!important` sans
   raison écrite), partout où l'invariant peut être violé (jumeaux : autre vue, autre thème, iPhone ET bureau).
3. Tes contrôles, et SEULEMENT eux (WOW23) : `npx eslint <tes fichiers>` ; `flake8` + `py_compile` sur tes fichiers
   Python ; LE test que tu répares. Pas de Docker, pas de suite voisine, pas de build du front ni de Playwright avant
   la poussée. `makemigrations --check`, les voisins et la suite entière : la CI. Modèle touché : migration additive.
4. UN commit par correction : « <id> — <ce que ça change pour l'utilisateur> », terminé par la ligne d'attribution
   donnée par le rappel système de la session (jamais une recopiée d'un ancien brief).

## 3. Trois sorties possibles par correction — jamais un « réglé » silencieux (une ligne `correction` chacune)
- **corrige** : test vert ; si la correction est VISIBLE, `gestes_apres` = les gestes exacts du constat d'origine, que
  la lane de couture rejouera sur l'instrument après le pli et la poussée (c'est elle qui prend et regarde la capture
  « après » : l'instrument ne sert que du code poussé).
- **conteste** : le constat est faux ou sans objet — la preuve (capture, code `fichier::symbole`, mesure).
- **impossible** : pas sans affaiblir un test, une règle ou une autre lane — pourquoi, et le plus petit changement
  qui débloquerait. Signaler vaut mieux que « régler » à moitié.
Besoin d'un changement dans un fichier d'une autre lane : une ligne `demande-croisee` (`ouverte`, `vers`, `fichier`,
`changement` exact), jamais l'édition.

## 4. Fautes qui ont rougi la CI des runs précédents — ne les refais pas
Exemples du module Tâches (19-20/11), à garder tant qu'ils s'appliquent au périmètre :
1. Spec e2e : jamais `setTimeout(` ni `page.waitForTimeout(` (garde ADEP24). Serveur lent simulé par une PORTE que le
   test lâche lui-même (`page.route` qui attend une promesse, assertions pendant, `lacher()`, assertions après).
2. axe-core : la CI joue SA version, pas celle du poste ; une spec a11y verte en local ne prouve rien. Le texte visible
   d'un bouton doit être un mot séparé de son `aria-label`.
3. Gardes qui lisent le code ligne à ligne : imports du module d'API sur UNE ligne chacun si la garde le demande ; une
   liste paginée se lit EN ENTIER ; tout paramètre de requête nouveau est déclaré sur la vue et lu par elle.
4. CSS du module : ses jetons (aucune couleur en dur, aucun `z-index` en dur), `:hover` sous `@media (hover: hover)`,
   requêtes média sous la forme exigée par la garde ; une règle qui regarde l'enveloppe de l'ERP ne fuit pas ailleurs.
5. Serveur : les tests de plafond de requêtes ; le schéma OpenAPI dit la vérité du serveur (sinon api-fuzz échoue sur
   « requête valide refusée ») ; un texte changé est cité par d'autres tests (`grep -rn "<phrase>" <tests>`).
6. Fichier de test NEUF : dis-le avec la raison (« Nouveau fichier car : ») ; sinon la garde de placement échoue.
7. Une spec lit des rôles, libellés et `data-*` : si tu en changes un (`grep -rn "<libellé>" frontend/e2e`), mets la
   spec à jour dans le même commit.
8. Les classes de défaut de CE run : lis leurs fiches (`<dossier>/classes/K-*.md`) ; chaque case de leur matrice que
   tes fichiers portent est à couvrir.
<Ajouter ici, à chaque tour, les classes de rouges CI vues au tour précédent (et les reporter à
`plan_drain_ci_bug_classes` à la rétro).>

## 5. Interdits
Fichiers hors de ta lane (une `demande-croisee` à la place) ; fichiers de l'orchestrateur (plan, `docs/CODEMAP.md`,
schéma OpenAPI) ; `git push`, `--amend`, `git stash`, rebase, docker, suite entière, build + Playwright local.

## 6. Rapport final (15 lignes au plus en message ; le détail dans ton fichier d'événements et `<dossier>/lanes/<id>.md`)
Branche + SHA de tête ; par correction : sortie (corrige / conteste / impossible), SHA, test (rouge → vert, commande et
résultat), gestes à rejouer après le pli ; ce qui n'a PAS été vérifié ; demandes croisées ouvertes ; tout défaut
voisin vu en passant.

## Test premier — brief du rédacteur des tests premiers (une section, pas un gabarit de plus)
- **Qui** : un agent sonnet, effort medium, UN par lane qui porte une classe ou un S1-S2 perte de données / chiffre faux.
- **Quand** : après la consolidation, AVANT le départ de sa lane.
- **Où** : son worktree isolé, branche `tests/T<n>-<id>` partie de `origin/<branche d'intégration>`, poussée ; c'est la
  branche d'où part la lane.
- **Quoi** : pour chaque classe, le test d'invariant qui itère la matrice de la fiche ; pour chaque S1-S2 désigné, le
  test qui rejoue le constat. Chacun ROUGE sur la tête actuelle (test qui exige une base : rouge lu dans la CI de la
  branche poussée, jamais sous Docker local ; sortie collée dans son fichier d'événements
  `<registre>/evenements/T<n>-tests-<id>.jsonl`, une ligne `test-premier` / `ecrit` par test), dans le module de test
  EXISTANT du fichier visé, sans toucher au code produit. Mêmes contrôles légers que la lane (§ 2.3), même § 4.
- **Rapport** : 10 lignes — branche, SHA, tests (chemin::nom, commande, sortie rouge), ce qui n'a pas pu être écrit.
