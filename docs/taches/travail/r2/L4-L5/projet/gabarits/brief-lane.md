# Brief commun des lanes de CORRECTION — <périmètre>, tour <n> (go-deep L4 / L5)

<Bloc d'ancrage de CLAUDE.md, mot pour mot.>

Ta lane : <id>, ses tâches de plan <ids>, ses fichiers (TU NE TOUCHES QUE CEUX-LÀ) : <liste>. Régime : <EXISTANT :
« corrige sans toucher au reste ; ne suppose jamais qu'une chose manque : cherche-la d'abord (grep) » | MIXTE : idem +
« suis le motif de `<fichier-patron>` ; liste à ne pas changer : <…> » | NEUF : « ne construis que les promesses de ta
lane ; le fichier de contrat `<…>` est l'interface »>.

## 0. Ton dossier (à respecter absolument)
- Worktree ISOLÉ, à toi seul (`git rev-parse --show-toplevel`). Chemins ABSOLUS et SOUS ton dossier pour Read / Edit /
  Write / Grep / Glob ; lectures permises au dehors : ce brief, la consolidation, le contrat, les rapports et captures
  des relecteurs. N'écris JAMAIS dans un autre worktree, même par Bash.
- Base : `git fetch origin <branche de tests>` puis `git checkout -B lane/T<n>-<id> origin/<branche de tests>` ;
  vérifie `git merge-base --is-ancestor <sha attendu> HEAD`, sinon arrête-toi et dis-le.
- Avant CHAQUE commit : `git branch --show-current` et `git rev-parse --show-toplevel` rendent les tiens.
- Front : `frontend\node_modules` est une JONCTION vers le dossier partagé (`cmd /c mklink /J …` si elle manque) ;
  n'y installe rien ; ne la retire que par `cmd /c rmdir` (jamais `rm -rf` : il viderait le dossier partagé).

## 1. Lire avant d'écrire
Le texte complet de chacune de tes tâches ; le constat d'origine et sa capture ; la fiche d'invariant de chaque classe
que tu touches (sa LISTE d'endroits violables est ta liste de travail, pas seulement le symptôme) ; les références du
périmètre ; chaque fichier touché EN ENTIER et ses appelants (`grep` du symbole côté front et serveur).

## 2. Corriger (A d'abord)
1. **Le test qui prouve** : pour un A ou une classe, il t'est DONNÉ (écrit par un autre, branche `<tests>`) et tu ne le
   modifies pas — le pli refuse ta lane si `git diff --name-only origin/<tests>..HEAD -- <fichiers de test donnés>`
   n'est pas vide. Sinon : écris-le rouge d'abord, dans le module de test EXISTANT du fichier touché.
2. Corrige à la RACINE (pas de pansement, pas de `setTimeout` pour masquer une course, pas de `!important` sans
   raison écrite), partout où l'invariant peut être violé (jumeaux : autre vue, autre thème, iPhone ET bureau).
3. Contrôles de ta lane, et seulement eux (WOW23) : `npx eslint <tes fichiers>` ; le test que tu répares ; serveur :
   `flake8` + `py_compile` + les tests sans base de ton module. Les voisins, la suite entière et les tests avec base :
   la CI. Modèle touché : migration additive, `makemigrations --check --dry-run` propre.
4. UN commit par correction : « <id> — <ce que ça change pour l'utilisateur> », terminé par la ligne d'attribution
   donnée par le rappel système de la session (jamais une recopiée d'un ancien brief).

## 3. Trois sorties possibles par correction — jamais un « réglé » silencieux
- **corrige** : test vert + (si visible) capture APRÈS regardée sur l'instrument, avec le geste du constat d'origine.
- **conteste** : le constat est faux ou sans objet — la preuve (capture, code `fichier::symbole`, mesure).
- **impossible** : pas sans affaiblir un test, une règle ou une autre lane — pourquoi, et le plus petit changement
  qui débloquerait. Signaler vaut mieux que « régler » à moitié.

## 4. Preuve sur l'écran réel (correction visible)
Construis TON front et sers-le sur TON port (<port>) avec le relais d'API de l'instrument (`instrument-de-revue.md`) ;
un script Playwright rejoue le geste avec TON compte (<compte>) ; capture APRÈS dans `<scratchpad>/lanes/<id>/`,
regardée. Moitié serveur : la preuve est le test serveur + le test front sur la forme servie ; écris « à rejouer après
le pli » avec les gestes exacts. Tue TON serveur de preview à la fin (le `node.exe` de TON port seulement). Ne touche
jamais aux conteneurs ni aux comptes des autres ; aucune commande `docker`.

## 5. Fautes qui ont rougi la CI des runs précédents — ne les refais pas
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
7. Une frappe ne se perd JAMAIS : toute écriture dans un champ contrôlé part de la valeur COURANTE (mise à jour
   fonctionnelle), jamais d'une valeur capturée avant un `await` ; le test tape la suite sans attendre.
8. Une spec lit des rôles, libellés et `data-*` : si tu en changes un (`grep -rn "<libellé>" frontend/e2e`), mets la
   spec à jour dans le même commit.
<Ajouter ici, à chaque tour, les classes de rouges CI vues au tour précédent (et les reporter à
`plan_drain_ci_bug_classes` à la rétro).>

## 6. Interdits
Fichiers hors de ta lane (écris ce qu'il faudrait, précisément, dans ton rapport) ; fichiers de l'orchestrateur
(plan, `docs/CODEMAP.md`, schéma OpenAPI) ; `git push`, `--amend`, `git stash`, rebase, docker, suite entière.

## 7. Rapport final (15 lignes au plus en message ; le détail dans `<dossier>/lanes/<id>.md`)
Branche + SHA de tête ; par correction : sortie (corrige / conteste / impossible), SHA, test (rouge → vert, commande et
résultat), capture APRÈS (chemin, ce qu'on y voit) ; ce qui n'a PAS été vérifié ; ce qui reste à rejouer après le pli ;
ce qu'il faut demander à une autre lane (fichier, changement exact) ; tout défaut voisin vu en passant.
