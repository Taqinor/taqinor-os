# Brief commun des lanes de CORRECTION r2 — module « Tâches » (TAQINOR OS)

Le module est construit, sur `main`, en production. Six relecteurs ont utilisé l'écran RÉEL et trouvé des défauts ;
ils sont consolidés, vérifiés contre le code et rangés en lanes dans
`C:\dev\taqinor-os\.claude\worktrees\erp-task-manager-ai-f8db1b\docs\taches\travail\r2\tour1\consolidation.md`
(identifiants `R2-NNN`). Tu corriges TA lane, à la racine, avec la preuve. Le fondateur (Reda, non-codeur, sur iPhone)
attend le niveau de Things 3 / Todoist / Linear : « the best in ease of use and prettiness ».

## 0. Ton dossier de travail (à respecter absolument)

Tu tournes dans un worktree git ISOLÉ, à toi seul : le dossier courant de ta session (`git rev-parse --show-toplevel`).
- Tous les chemins passés à Read / Edit / Write / Grep / Glob sont ABSOLUS et SOUS ton dossier. Seules lectures permises
  hors de ton dossier : ce brief, `consolidation.md`, les rapports `tour1/*.md`, `pile-locale.md`, et les captures des
  relecteurs (`…\scratchpad\r2\<nom>\`). N'écris JAMAIS dans un autre worktree, même par Bash.
- Base : `git fetch origin dev-taches-r2` puis `git checkout -B lane/r2-<ta lane> origin/dev-taches-r2`. Vérifie que
  `git merge-base --is-ancestor efc5075e4 HEAD` réussit ; sinon arrête-toi et dis-le.
- Avant CHAQUE commit : `git branch --show-current` rend ta branche, `git rev-parse --show-toplevel` rend ton dossier.
- Front : `frontend\node_modules` est une JONCTION vers `C:\dev\taqinor-os\frontend\node_modules`
  (`cmd /c mklink /J frontend\node_modules C:\dev\taqinor-os\frontend\node_modules` si elle manque). N'y installe rien,
  ne la supprime jamais avec `rm -rf` (ça viderait le dossier partagé) : `cmd /c rmdir frontend\node_modules`.

## 1. Lire avant d'écrire

- Dans `consolidation.md` : le texte complet de CHACUNE de tes corrections (cause, correction proposée, preuve
  attendue, fichiers) et la section « Choix à faire » (les choix y sont TRANCHÉS : applique la recommandation, ne
  rouvre pas le débat). Le constat d'origine dans le rapport du relecteur cité, et sa capture, si le texte ne suffit pas.
- `docs/taches/reference/{textes,regles,api,donnees}.md` dans ton dossier : les libellés (tutoiement, au caractère
  près) et les règles font foi. Si ta correction CHANGE un libellé, une règle ou une forme d'API, mets à jour la
  référence dans le même commit (c'est permis ici, contrairement aux fusions précédentes).
- Les maquettes `docs/taches/maquettes/*.html` + `taches.css` pour l'apparence.
- Les fichiers que tu touches, EN ENTIER, avant de les modifier ; et leurs appelants (`grep` du symbole dans
  `frontend/src` et `backend/django_core`) : une correction qui casse un autre écran est pire que le défaut.

## 2. Corriger, correction par correction (A d'abord)

1. REPRODUIS d'abord : un test automatique qui échoue pour la bonne raison (module de test EXISTANT du fichier touché,
   `*.test.jsx` voisin, `apps/taches/tests/test_*.py` existant ; un nouveau fichier de test seulement s'il n'en existe
   aucun pour ce module, et tu le dis dans le rapport). Pour un défaut purement visuel (CSS), la preuve est la capture
   avant / après (§ 3), pas un test de regex sur le source.
2. Corrige à la RACINE (pas de pansement, pas de `setTimeout` pour masquer une course, pas de `!important` hors
   nécessité expliquée). La plus petite correction qui règle le problème partout où il se pose (cherche les jumeaux :
   le même défaut dans la feuille voisine, l'autre vue, l'autre thème, iPhone ET bureau).
3. Test vert, puis les voisins : `npx eslint <tes fichiers>` ; `npm run test:unit -- <fichiers de test touchés et
   voisins> --testTimeout=30000` (depuis `<ton dossier>\frontend` ; jamais la suite entière, aucun vitest laissé en
   arrière-plan). Serveur, depuis `<ton dossier>\backend\django_core` (PowerShell) :
   `$env:PYTHONPATH='C:\dev\wpstub'; $env:PYTHONIOENCODING='utf-8'; & "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" manage.py check`
   + `flake8` + `py_compile` ; les tests SANS base tournent (`manage.py test <module>` pour un `SimpleTestCase`) ; les
   tests AVEC base ne tournent pas sur l'hôte (la CI les joue) : écris-les avec soin, relis chaque fabrique contre
   `tests/fabriques.py`, aucune horloge vivante, jamais d'attribut de classe `client` dans un `TestCase`.
   Modèle touché : migration additive, numérotée à la suite, `makemigrations --check --dry-run` propre.
4. UN commit par correction (ou par petit groupe de corrections indissociables) : « R2-NNN — <ce que ça change pour
   Reda> », terminé par `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## 3. Preuve sur l'écran réel (obligatoire pour toute correction visible)

Une pile locale tourne (lis `pile-locale.md`) : Django sur `http://127.0.0.1:8010` sert le code de `main` (PAS le tien).
- Correction FRONT seule : construis TON front (`npm run build` dans `<ton dossier>\frontend`, ~1-2 min) et sers-le sur
  TON port (donné dans ton prompt) :
  `cmd /c "set E2E_PROXY=1&& set E2E_API_TARGET=http://127.0.0.1:8010&& node_modules\.bin\vite.cmd preview --port <port> --host 127.0.0.1 --strictPort"`
  en arrière-plan ; puis un script Playwright (`C:\dev\taqinor-os\frontend\node_modules\playwright`, iPhone 390×844
  tactile échelle 2 et bureau 1440×900, clair et sombre quand la couleur est en jeu) rejoue le geste du constat avec
  TON compte (donné dans ton prompt ; `bash <chemin r2>\reinit-compte.sh <compte> [HH:MM|--vide]` pour le remettre à
  neuf) et prend la capture APRÈS, que tu REGARDES (Read). Captures et scripts dans
  `C:\Users\kasri\AppData\Local\Temp\claude\75bbe857427ccce5\b797bc27-f912-4ba8-a54b-d982221d7224\scratchpad\r2\lanes\<ta lane>\`
  (écris-y par Bash si l'outil Write refuse). Une correction dont la capture « après » ne montre pas le défaut réglé
  n'est PAS faite. TUE ton serveur de preview à la fin (le `node.exe` de TON port seulement).
- Correction qui a une moitié SERVEUR : la pile ne sert pas ton code Python ; la preuve est le test serveur + le test
  front sur la forme servie ; dis dans ton rapport « à rejouer sur l'écran après le pli » avec les gestes exacts.
- Ne touche jamais aux conteneurs (`taches-r2-*`, `erp-agentique-*`), ni au serveur du port 5180, ni aux comptes
  des autres. Aucune commande `docker compose`.

## 4. Règles de maison (rappel)

- Tout filtré par société ET propriétaire via les sélecteurs existants ; `company` jamais lue du corps de requête.
- Aucun import de `models`/`views` d'une autre app métier ; aucun chiffre ni libellé inventé (un constat affiché est
  calculé des données ou omis) ; aucun `except`/`catch` nu ou vide ; aucun `skipTest` ; aucune dépendance nouvelle.
- Front : tout sous `.tch`, couleurs par jetons `--tch-*` (aucun hex, aucun z-index en dur), `:hover` sous
  `@media (hover: hover)`, cibles tactiles ≥ 44 px, animations sous `prefers-reduced-motion: no-preference`,
  `toISOString().slice(0,10)` interdit (`.split('T')[0]`), imports de `tachesApi` sur UNE ligne par import, une erreur
  s'affiche sous le champ fautif, une liste ne se vide jamais sur un rafraîchissement en échec, un geste est
  OPTIMISTE (l'écran suit tout de suite, réconciliation au retour, « Annuler »), aucun raccourci clavier destructif.
- Tu ne touches QUE les fichiers de ta lane (table de `consolidation.md`). Un fichier d'une autre lane doit changer ?
  Ne le touche pas : écris dans ton rapport ce qu'il faudrait, précisément. Fichiers HORS du module Tâches
  (`styles/deploy/*`, barre de l'ERP, `features/ia`, `apps/agent`, `fastapi_ia`) : interdits sauf s'ils sont nommés
  dans ta lane ; préfère une règle sous `.tch` dans le CSS du module.
- Interdits : `docs/plans/PLAN_TACHES.md`, `docs/CODEMAP.md`, `docs/openapi-schema.yml` (l'orchestrateur le fait),
  `git push`, `--amend`, `git stash`, rebase, docker, suite de tests entière.
- Les specs `frontend/e2e/taches-*.spec.js` et `e2e/acceptation/tch*.spec.js` s'appuient sur des rôles, libellés et
  attributs `data-*` : si tu changes un libellé, un rôle ARIA ou une structure qu'une spec lit
  (`grep -rn "<libellé>" frontend/e2e`), mets la spec à jour dans le même commit.

Un vrai blocage sur une correction : ne la bâcle pas ; écris pourquoi et passe à la suivante.

## 5. Rapport final (court)

La branche, le SHA de tête, puis par correction : SHA, fichiers, test écrit (rouge avant → vert après, commande et
résultat), capture « après » (chemin) et ce qu'on y voit, ce qui n'a PAS pu être vérifié, ce qui reste à rejouer après
le pli, et tout ce que tu as vu d'autre en passant (défaut voisin non corrigé, fichier d'une autre lane à changer).

---

## Vague 3 — corrections du TOUR 2 (identifiants `R3-NNN`)

Tout ce qui précède reste vrai, avec ces changements :
- Ta liste de travail est dans `…\r2\tour2\consolidation.md` (pas `tour1`) : § 0 (les six sujets majeurs M1-M6 : la
  conception d'ensemble à respecter), § 1 (le texte de chacune de tes corrections `R3-NNN`), § 3 (choix C-13 à C-24 :
  TRANCHÉS, applique la recommandation), § 4 (ta fiche de lane et la table fichier → lane : tu ne touches QUE tes
  fichiers). Lis aussi `…\r2\vague3-ajouts.md` : s'il nomme un de TES fichiers, la correction est à toi.
- Base : `git fetch origin dev-taches-r2 && git checkout -B lane/r3-<ta lane> origin/dev-taches-r2` ; vérifie
  `git merge-base --is-ancestor 2d65165d6 HEAD`.
- Les références `docs/taches/reference/*.md` se mettent à jour dans le MÊME commit que le libellé, la règle ou la
  forme changés (le code fait foi, la référence dit ce qui est servi et affiché).
- Une correction qui dépend du CONTRAT d'une autre lane (dit dans ta fiche : « après le contrat de L1 », « après le
  pli de L5 ») se fait EN DERNIER : l'orchestrateur te préviendra par message quand la base est prête
  (`git fetch origin dev-taches-r2 && git merge --no-edit origin/dev-taches-r2`, jamais de rebase). Si tu arrives au
  bout de ta liste sans ce message, rends ton rapport en disant ce qui reste et pourquoi.

Fautes qui ont rougi la CI de la vague précédente — ne les refais pas :
1. **Spec e2e** : jamais `setTimeout(` ni `page.waitForTimeout(` (garde ADEP24, liste d'exceptions fermée). Pour
   simuler un serveur lent : une PORTE que le test lâche lui-même
   (`let lacher; const porte = new Promise((r) => { lacher = r }); await page.route(motif, async (route) => { await porte; await route.continue() })`,
   assertions pendant que la requête est retenue, `lacher()`, assertions après).
2. **axe-core** : la CI joue axe 4.14.0, le poste 4.12.1 (une spec axe verte ici ne prouve rien). Un bouton dont le
   texte visible n'est pas un MOT séparé de son `aria-label` est refusé (« Notifications (14) » avec la pastille « 14 »
   → écrire « Notifications : 14 »). Pour vérifier : `…\scratchpad\r2\orchestrateur\axe414\package\axe.min.js`
   (`page.addScriptTag` puis `axe.run(el, { runOnly: [règle] })`, exemple dans `axe-cloche3.cjs` à côté).
3. **`api/tachesApi.js`** : chaque `import { … } from '…/tachesApi'` tient sur UNE ligne (plusieurs imports d'une
   ligne si c'est long) ; une liste paginée se lit EN ENTIER (`listerTous…` / `toutesLesPages`), jamais la page 1 ; un
   appel dont les arguments ne sont pas lisibles statiquement porte « // parametres-requete: » au-dessus ; tout
   paramètre de requête nouveau est DÉCLARÉ sur la vue (`OpenApiParameter`) et lu par elle.
4. **CSS** : aucun `z-index` en dur, pas même `auto` (jetons `--tch-z-*`, `isolation`, ou rien) ; aucune couleur en
   hex ; `:hover` sous `@media (hover: hover)` ; jamais `@media (max-width: 768px)` tel quel (`screen and (…)`) ; une
   règle qui regarde l'enveloppe de l'ERP s'écrit `.layout:has(> .layout-main > .layout-content > .route-fade > .tch)`,
   jamais `.layout:has(.tch)`.
5. **Serveur** : un test de plafond de requêtes existe par lecture (`tests/test_plafonds.py`) : n'ajoute aucune
   requête à une lecture sans le dire ; le schéma OpenAPI doit dire la vérité du serveur (toute contrainte d'un champ
   de requête déclarée sur le sérialiseur : sinon api-fuzz échoue sur « requête valide refusée ») ; un texte de
   gabarit changé a des tests qui le citent ailleurs (`grep -rn "<phrase>" backend/django_core/apps/taches/tests`).
6. **Fichier de test NEUF** : dis-le dans ton rapport avec la raison en une phrase (l'orchestrateur l'inscrit au plan,
   sinon la garde de placement des tests échoue).
7. **Une frappe ne se perd JAMAIS** : toute écriture dans un champ contrôlé part de la valeur COURANTE (mise à jour
   fonctionnelle), jamais d'une valeur capturée avant un `await` ; le test tape la suite sans attendre.
