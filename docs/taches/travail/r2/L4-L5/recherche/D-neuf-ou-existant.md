# Lane D — NEUF ou EXISTANT : ce que change le régime, et comment le détecter (20/11/2026)

Web : 17 appels sur les 20 du plafond partagé (3 en échec DNS : martinfowler.com, understandlegacycode.com). « lu » = page lue
cette session ; « résumé » = seulement le résumé d'une recherche (pas la page) ; « mémoire » = de mémoire, à vérifier.
Dépôt : tout ce qui est chiffré ci-dessous vient d'une commande lancée sur `origin/main` ce 20/11 (git ls-tree / git show / gh pr view).

## 1. L'essentiel en dix lignes
1. Les sources sérieuses ne décrivent pas un « mode neuf » et un « mode existant » symétriques : l'existant se distingue par
   **ce qu'on doit prouver AVANT de toucher** (comportement actuel figé), le neuf par **ce qu'on doit décider AVANT de coder**
   (contrat, conception). Notre session du 17-20/11 a vécu exactement ces deux régimes (PASSATION §3 vs RETRO §2).
2. Détecter le régime = un sondage de < 1 minute sur des **identifiants légers** (chemins, comptes, cases cochées), pas une lecture
   (Anthropic, « context engineering », lu). Je l'ai fait tourner : voir §4.2.
3. **Le piège n° 1, prouvé sur pièces : lire le worktree au lieu de `origin/main`.** Ce worktree n'a PAS `apps/taches` ; `origin/main`
   en a 203 fichiers backend + 119 front + 49 de tests. Un agent lisant le dossier local classerait « Tâches » NEUF.
4. Le piège n° 2, prouvé : le **nom d'une fonction n'est pas le nom d'un dossier** (« copilote » : 11 mentions CODEMAP, 0 fichier
   sous ce nom ; il vit dans `agent`, `crm`, `fastapi_ia`). C'est le cas MIXTE typique.
5. Règle proposée : classer **promesse par promesse** (technique de `etat-des-lieux.md`, r2 étape 0), pas module par module ; la part
   de promesses déjà servies par le code décide NEUF / MIXTE / EXISTANT. Seuils = ma proposition, à calibrer (aucune source).
6. Une seule ligne d'annonce + imposition par l'utilisateur (comme le niveau nommé de go-deep) ; jamais une question (règle Reda).
7. Refonte vs retouche : la littérature (Spolsky 2000, Fowler) penche pour la retouche incrémentale ; la maison a déjà un
   étrangleur réel (`USE_PREMIUM_QUOTE_ENGINE`, CLAUDE.md règle 4). Une « refonte » = EXISTANT en mode étrangleur, jamais NEUF.
8. Contradiction à retenir : BMAD (docs actuelles) dit que les cartes de dépôt qui répètent le code **vieillissent** ; notre CODEMAP
   fait 2 077 lignes. On l'utilise pour l'EXISTENCE (gardée par empreinte CI), la preuve reste `git ls-tree`.
9. Spec Kit n'a qu'UN flux pour neuf et changement ; nos deux régimes se justifient par l'historique, pas par la théorie.
10. Le détecteur se trompe dans 5 cas listés §4.6 ; la parade est l'annonce + l'imposition + la bascule en cours de route.

## 2. Pratiques à adopter
| Pratique | Source (lu / mémoire) | Mécanisme | Ce qu'elle aurait changé (RETRO §) | Coût | Niveau |
|---|---|---|---|---|---|
| Classer par **promesses** de la demande contre le code | Maison : `r2/etat-des-lieux.md` ; BMAD « Start in an Existing Codebase » : l'entrée dépend de la taille du changement, `bmad` « inspecte le projet » (docs.bmad-method.org, lu) | décomposer la demande en promesses, marquer chacune absente / partielle / servie | r2 l'a fait à la main à l'étape 0 ; ici il décide du régime avant tout | 1 haiku, ~5 min | L4, L5 |
| Sondage d'existence sur `origin/main` en identifiants légers | Anthropic « Effective context engineering » : identifiants légers + exploration à la demande, hybride (lu, 2025) | `git ls-tree` + 6 greps → 6 nombres (§4.2) | évite la classification sur worktree périmé (§1.3) | ~secondes | L4, L5 |
| Figer le comportement actuel AVANT retouche (tests de caractérisation / goldens des chiffres servis) | Feathers, *Working Effectively with Legacy Code* 2004 (mémoire + résumé de recherche, livre NON lu) ; mode d'emploi agents : developertoolkit.ai « Characterization tests » (lu, blog non daté) : goldens enregistrés sur le commit intact, quirks notés sans les corriger, preuve par mutation que le golden peut échouer, goldens verrouillés en CI | un golden par chiffre/geste servi, enregistré avant la vague 1 | §4 : 3 régressions sur 191 contre-vérifications (tour 1), 2 au tour 2 ; §6.1 « la même classe revenue 4 fois » | moyen : 1 lane sonnet au tour 0 | L5 (L4 : seulement les chiffres servis) |
| Suivre le motif existant, citer le fichier modèle (MIXTE) | Claude Code best-practices : « follow the pattern in HotDogWidget.php… no new libraries » (code.claude.com, lu) ; BMAD : `bmad-build` « investigue le dépôt, note ce qu'il faut réutiliser et ne pas changer » (lu) | le brief de lane MIXTE nomme le fichier-patron et la liste « à ne pas changer » | évite la « 2e façon de faire » (couture §6.2) | nul | L4, L5 |
| Contexte de projet COURT et vérifié, pas un arbre de doc | BMAD « Theory of project context » (lu, docs actuelles) : l'ancien `document-project` = « large, non vérifié, périmé »; on ne garde que ce qui est coûteux à redécouvrir ; un rafraîchissement ne doit jamais grossir le bloc | le sondage lit la carte pour l'existence, vérifie au dépôt, ne recopie rien | §6.8 (orchestrateur à 90 % de contexte) | nul | L4, L5 |
| Étrangleur pour toute « refonte » | Fowler, *Strangler Fig Application* 2004/2019 (résumé de recherche ; page non lue : DNS) : façade, bascule route par route, chaque pas réversible, la base de données est la partie dure | nouveau derrière un interrupteur, ancien gardé, bascule par écran | maison : `USE_PREMIUM_QUOTE_ENGINE` ; module « invisible jusqu'à activation » (PLAN_TACHES, `installable: False`) | élevé | L5 |
| Évaluation d'usage à 3-5 évaluateurs indépendants, documents cachés jusqu'à la fin | NN/g « How to conduct a heuristic evaluation » (lu) : 3 à 5 personnes, seules, 1-2 h, chacune parcourt la tâche puis note les écarts | = nos relecteurs neufs à comptes séparés (r2 §2.2) ; confirme 4-6 relecteurs | confirme r2 ; ajoute « cacher les rapports des autres tant que l'un écrit » | nul | L4, L5 (EXISTANT) |
| Carte de symboles classée par références (accélérateur) | Aider « repo map » (aider.chat, lu) : graphe fichiers/dépendances, budget ~1 k tokens par défaut | déjà proposé par CLAUDE.md (Serena MCP) | recherche de coutures plus courte en EXISTANT/MIXTE | à approuver | L5 |

## 3. Pièges et contre-indications
- **Spolsky, « Things You Should Never Do, Part I » (2000, lu)** : réécrire de zéro est « l'une des pires erreurs stratégiques » ; le vieux
  code laid contient des correctifs de cas réels (installation sans IE, mémoire faible) ; exemples Netscape 6 (jamais de v5), Borland
  dBase/Quattro Pro, Word « Pyramid » arrêté. Source ancienne, argument d'opinion + anecdotes, pas une mesure. Contre-argument interne :
  aucun ; r2 a retouché un module « fini » et trouvé 152 constats, preuve que l'existant se corrige par tours, pas qu'il se jette.
- **Spec Kit (github/spec-kit `spec-driven.md`, lu, non daté) contredit nos DEUX régimes** : un seul flux (idée → PRD → plan → tâches → code)
  pour tout ; l'amélioration = « revisiter la spécification » ; le brownfield n'est pas traité. Lecture : ne pas dédoubler la méthode sans
  preuve. Notre preuve = l'historique du 17-20/11 (§4.4), pas une théorie. À défaut de cette preuve, le plus sûr serait un flux unique.
- **BMAD (docs actuelles, lu)** : l'ancien flux brownfield `document-project` est **déprécié** ; sources plus anciennes (guides 4.x, résumé de
  recherche) le décrivent encore : version-dépendant, ne pas copier un guide ancien. Les docs affirment que des fichiers de contexte qui
  répètent le dépôt n'ont donné « aucun gain de succès et ~20 % de coût en plus » : étude non nommée dans la page → douteux, à ne pas citer comme chiffre.
- **Golden = piège de l'oracle** (developertoolkit, lu) : enregistrer APRÈS la retouche, lancer les drapeaux de mise à jour des snapshots
  pendant la retouche, ou figer des bugs comme spécification permanente. Contre-mesure maison : golden daté du commit intact, jamais mis à jour
  par la lane qui retouche.
- **Notre CODEMAP contredit BMAD** : §4 est un long texte de paraphrase (2 077 lignes) ; BMAD dit que « structure et cartes » vieillissent le plus
  vite. Atténuation réelle : empreinte de structure vérifiée en CI (`codemap_fingerprint.py --check`) ; mais la ligne `taches` de §3/§4 peut
  dire vrai sur l'existence tout en étant fausse sur l'état. D'où : carte = indice, `git ls-tree` = preuve.
- **Kiro** : fichiers de pilotage `product.md` / `tech.md` / `structure.md` (kiro.dev/docs/steering, lu) ; la page ne dit rien de l'amorçage sur
  dépôt existant : n'en tirer aucune règle brownfield.

## 4. Neuf ou existant

### 4.1 Ce que disent les sources, en une phrase chacune
BMAD : le point d'entrée dépend de la taille du changement, pas d'un « type de projet » (lu). Spec Kit : un seul flux (lu). Feathers :
l'existant se change après avoir figé son comportement actuel (mémoire). Fowler : une refonte est une suite de pas réversibles derrière une
façade (résumé). NN/g : l'existant s'audite par l'usage, à plusieurs évaluateurs indépendants (lu). Claude Code : donner le fichier-patron
et une vérification ; une spec écrite d'abord quand on ne sait pas ce qu'on veut (lu). Aucune ne fournit un détecteur automatique : **la
détection est à construire, sur nos signaux** (rien trouvé à citer).

### 4.2 Signaux lisibles en moins d'une minute (tous sur `origin/main`, jamais sur le worktree)
Sondage que j'ai lancé (`m` = nom du module/fonction ; `git ls-tree -r --name-only origin/main`, `git show origin/main:<fichier>`) :
| Signal (force) | Commande | taches | calepinage | copilote | zzznouveau |
|---|---|---|---|---|---|
| mentions dans `docs/CODEMAP.md` (indice) | `git show origin/main:docs/CODEMAP.md \| grep -ci "\bm\b"` | 5 | 63 | 11 | 0 |
| fichiers sous `apps/m/`, `features/m/`, `pages/m/` (FORT) | `ls-tree … \| grep -E "^(backend/django_core/apps/m/\|frontend/src/(features\|pages)/m/)"` | 344 | 1 070 | **0** | 0 |
| dont fichiers de test (moyen) | idem `\| grep -E "test\|spec"` | 82 | 606 | 0 | 0 |
| specs e2e `frontend/e2e/*m*` (moyen) | `ls-tree … frontend/e2e` | 10 | 4 | 0 | 0 |
| plan à son nom + cases `[x]` (FORT) | `ls-tree docs/plans` ; `grep -c "^- \[x\]"` | 1 plan ; **200 cochées, 0 ouvertes** | 1 | 0 | 0 |
| propriétaire dans `docs/ownership.yml` (moyen) | `grep -c "apps/m/"` ; `python scripts/check_ownership.py --owner-of <chemin>` | 1 | 3 | 0 | 0 |
Autres signaux, non sondés ici : mergée dans une PR (`git log --first-parent origin/main -- <chemin>` : taches = 6 commits de premier niveau,
17 → 20/11) ; interrupteur / droit d'activation (`taches_voir` accordé au seul Administrateur) ; dossier de conception `docs/taches/` ; marque
« parqué » (`core/parked.py`).
**« En ligne ? » n'est pas lisible dans le dépôt** : merge ≠ déployé (CLAUDE.md « Deploys », mémoire 17/11 auto-deploy arrêté). On lit donc
l'**activation** (droit, interrupteur, `installable`), pas le déploiement ; lire la prod = geste à demander (accord « lecture prod » existe, coûteux).
Signaux de la DEMANDE : verbes neufs (« construis / crée / ajoute / je veux un… ») ; verbes d'existant (« améliore / revois / corrige / refais /
polis / look at what was done / redo ») ; nom d'un module existant ; mots d'incident (« incident du 19/11 »). Ce sont des indices ; la preuve est
la décomposition en promesses (4.3).
Piège de mesure : une table paresseuse du genre « 0 fichier → NEUF » échoue pour `copilote` (0 fichier, mais code réel ailleurs) ; d'où la
décomposition en promesses plutôt qu'un seuil sur un nom.

### 4.3 Règle de décision (à trois issues) — seuils proposés, à calibrer
1. Écrire la liste des **promesses** de la demande (une phrase chacune, 5-15). 2. Pour chacune, une preuve : route / écran / action / test qui la
sert (grep ciblé via CODEMAP §4-§5 puis `git ls-tree`), sinon « absente » ; « partielle » si le geste existe mais pas le cas demandé.
3. Part servie P = (servies + ½ partielles) / total. **NEUF** : P < ~20 % ET aucun module ne couvre le sujet (≥ 2 signaux FORTS absents).
**EXISTANT** : P > ~80 % (la demande porte sur la qualité : verbes d'existant) **MIXTE** : entre les deux, ou fonction neuve dont le point d'accueil existe
(app + fichier-patron). 4. Le verbe ne décide jamais seul : « refais Tâches » = EXISTANT (P ≈ 100 %), pas NEUF.

### 4.4 Ce que chaque issue change (déroulé fondé sur ce qui s'est passé)
| | **NEUF** (Tâches 17-18/11) | **EXISTANT** (Tâches r2 19-20/11) | **MIXTE** (fonction neuve dans un module existant) |
|---|---|---|---|
| Ordre | références + recherche (`recherche-2…8`) → conception (`socle`, `spec-2…8`, arbitrages A1-A18) → maquettes (81) → **contrat d'abord** (PACT10) → plan + claims → fusions F1-F4 | état des lieux promesse par promesse → pile privée → tour de relecteurs neufs sur l'écran réel → consolidation → lanes → pli → tour suivant → critique du diff | état des lieux **de la seule surface touchée** → contrat de la moitié neuve → lane unique (brief « fichier-patron + à ne pas changer ») → couture |
| À sauter | tours de relecteurs sur usage (rien à utiliser avant le premier écran) ; caractérisation | références et maquettes (sauf pour une page vraiment neuve) ; contrat d'abord (sauf changement d'API) | tour complet de relecteurs (sauf si l'écran touché est central) |
| Preuves exigées | contrat partagé testé des deux côtés ; acceptation en direct par fusion (acceptation-f2/f3) ; critique du diff ; module **invisible** jusqu'à activation | capture avant/après regardée ; goldens inchangés (§2) ; zéro A « avant le merge » ; contre-vérification par des NEUFS | test rouge d'abord ; goldens de la surface touchée inchangés ; fichiers étrangers en AJOUT seul |
| Risque propre | page blanche : inventer, sur-spécifier, 324 fichiers / +42 132 lignes d'un coup (PR #1447) ; frange MIXTE (fichiers d'autres propriétaires, liste « ajout seulement » de PLAN_TACHES) | **régression** (3 puis 2 constatées), « corriger à moitié » (≈ 25 %), envie de réécrire (Spolsky), coutures entre lanes | deux façons de faire côte à côte ; fonction neuve qui casse l'ancienne ; propriété des fichiers |
| Critère de sortie | contrats verts + acceptations + 0 bloquant à la critique | règle « avant le merge » seulement, sortie chiffrée décidée au tour 0 (RETRO §6.5) | la fonction neuve passe SES acceptations ET les goldens de l'ancien tiennent |

### 4.5 Ligne d'annonce (une ligne, puis on avance)
« Régime : EXISTANT — `taches` existe sur `origin/main` (344 fichiers, 82 tests, 200/200 cochées, mergé 20/11) ; demande = « refaire / polir » ;
promesses servies ≈ 90 %. Je pars de l'usage. Dis « neuf » / « mixte » pour imposer. » (même gabarit pour NEUF et MIXTE : le NEUF dit
« aucun module trouvé : p. 0 fichier, 0 plan, 0 propriétaire »).

### 4.6 Trois exemples de l'historique réel, classés par la règle
- **A. Module Tâches, 17/11 → NEUF.** Demande (PASSATION §0) : « SON gestionnaire de tâches et de projets… le meilleur, en une fois ». Signaux : 1re
  apparition de `apps/taches` sur `main` le 17/11 (PR #1447), aucun propriétaire ni ligne CODEMAP avant ; verbe « veut ». Réel : conception →
  81 maquettes → F1 invisible (324 fichiers, +42 132 lignes) : conforme au déroulé NEUF.
- **B. Module Tâches, 19-20/11 → EXISTANT.** Demande : « look at what was done, and redo multiple rounds » ; signaux §4.2 (344 / 82 / 10 e2e / 200
  cochées / ligne CODEMAP + routes). Réel : état des lieux, pile privée, 3 tours, PR #1481 (246 fichiers, +22 958 / −4 029) : conforme.
- **C. PR #1485 « Copilote : déléguer ses dossiers et retrouver un collègue par son nom » (19/11) → MIXTE.** « déléguer » est une capacité nouvelle ;
  le Copilote existe (CODEMAP « Copilote commercial 14/11 ») mais sans dossier à son nom ; la PR touche `apps/agent`, `apps/crm`, `fastapi_ia`,
  `capacites.yml`, `manuel.md` (21 fichiers, +532/−48). Cadre : fichier-patron, pas de tour complet.
- Contrepoint de taille : PR #1494 « les informations au-dessus du devis se replient » (2 fichiers `pages/crm`, +62/−10) → EXISTANT **léger** ;
  le régime fixe l'ordre des étapes, pas leur volume (go-deep L1-L3 fixe le volume).

### 4.7 Quand la règle se trompe, et la parade
1. **Worktree périmé** (prouvé §1.3) → toujours `git fetch` + lire `origin/main`; l'annonce cite le SHA lu.
2. **Nom ≠ dossier** (prouvé : copilote) → décomposition en promesses, grep de CODEMAP §4 par mot, pas par chemin.
3. **Coquille « parquée »** : dossier présent mais sans routes ni tests (47 apps, CODEMAP §3 ; registre `core/parked.py`) → ni NEUF ni EXISTANT : restauration
   (recette éprouvée `docs/parked-modules.md`) ; ranger en NEUF avec l'archive comme référence.
4. **Plan écrit, rien construit** (ex. YanBow, 06/10 : 51 tâches, « rien construit » selon la mémoire) → le fichier de plan existe mais 0 case cochée = NEUF ;
   à l'inverse du code « éteint par interrupteur » (Copilote, contact parqué) = EXISTANT sans utilisateurs : risque de régression moindre, données absentes.
5. **Demande mixte / verbe trompeur** (« refais » un module que l'on veut vraiment changer de fond) → promesses : si P > 80 % mais l'utilisateur veut une refonte,
   c'est un étrangleur (EXISTANT + interrupteur), à annoncer comme tel.
Parade générale : (a) annonce d'une ligne (§4.5), (b) l'utilisateur impose « neuf / existant / mixte » (prioritaire comme le niveau nommé),
(c) **bascule en cours de route** dès que R1 contredit le classement (module découvert, API inexistante) avec une ligne ; (d) aucune question
(Reda : « je ne veux plus de questions »).

## 5. Critères de sortie et mesures (ce que disent les sources)
- developertoolkit (lu) : « assez » = goldens sur commit intact, 2 passages identiques, couverture de branches du point de couture expliquée, score de mutation
  au-dessus du plancher, chaque « quirk » avec un responsable et une date, goldens verrouillés en CI et contre l'édition par l'agent ; définition de fini
  unique : suite verte ET goldens inchangés.
- BMAD (lu) : un bloc de contexte rafraîchi ne grossit pas ; chaque ligne doit encore changer un comportement. Rien sur la fin d'un chantier.
- NN/g (lu) : pas de seuil chiffré de « fini » ni de sévérité dans la page. Notre critère interne (zéro A avant le merge) reste sans source externe.
- Fowler (résumé) : fini quand plus rien ne dépend de l'ancien système ; pas de critère chiffré.

## 6. Non couvert, non trouvé, douteux
- Feathers : livre non lu ; « points de couture » et « sprout / wrap » seulement par résumés secondaires de recherche (daedtech, bssw…), à vérifier.
- Fowler : page non lue (DNS), résumé de recherche seulement ; l'ordre « base de données = partie dure » vient de ce résumé.
- Aucune source trouvée sur la détection AUTOMATIQUE neuf/existant ; §4.2-4.3 est une conception maison, non éprouvée. Les seuils 20 % / 80 % sont des hypothèses.
- Non traité : « product teardown » / inventaire fonctionnel par l'usage d'un produit tiers (pas de source lue) ; décider « refonte ou retouche » en équipe (au-delà de
  Spolsky et du résumé Fowler) ; analyse d'impact (non cherchée) ; Spec Kit brownfield (la page ne le traite pas).
- BMAD : chiffre « ~20 % de coût en plus » = étude non nommée par la page ; developertoolkit = blog commercial non daté, pratique plausible mais non indépendante.
- Les tests locaux n'étant pas lancés (lecture seule), aucune affirmation de ce rapport ne repose sur l'exécution du code du module.
