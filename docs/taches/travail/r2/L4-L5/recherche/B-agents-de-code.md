# Lane B — agents de code : comment les équipes les font tourner de bout en bout (hors Anthropic)

Recherche du 20/11/2026. « lu » = lu dans la page cette session ; « mémoire » = de mémoire, à vérifier ; « secondaire » = lu seulement
chez un tiers. 4 recherches web + ≈ 25 pages lues. Les liens sont donnés en toutes lettres.

## 1. L'essentiel en dix lignes
1. Aucune méthode lue ne fait ce que la rétro a fait (relecteurs neufs sur l'écran RÉEL, avec preuve) : toutes vérifient par tests,
   lint, typecheck, build ou revue de diff. Notre étage « usage réel » est l'originalité de L4 ; il n'est dans aucune source lue.
2. Toutes les boucles sérieuses ont une règle d'arrêt MÉCANIQUE, écrite avant de commencer : `passes: true` + 10 itérations max
   (Ralph de snarktank), « done when » + commandes de validation par jalon (Codex), 5 tours max par tâche puis disjoncteur
   (Superpowers). La rétro s'arrête sur « avant le merge seulement » (§3) : bonne règle, mais sans plafond de tours ni disjoncteur.
3. Les artefacts durables sont petits, tenus au fil de l'eau, et séparés par rôle : spec figée / plan à jalons / mode d'emploi /
   journal (Codex, 4 fichiers) ; liste de tâches à état + notes ajoutées seulement (Ralph) ; règles apprises (Every, Ralph).
4. Les méthodes à spécification (Spec Kit, Kiro) sont jugées TROP LOURDES pour un petit changement et pour l'existant par
   la seule évaluation indépendante lue (Böckeler, 15/10/2025) : 4 récits et 16 critères pour un petit bug. Elles servent le NEUF.
5. Pour l'existant, les sources distinguent un autre geste : « établir un contexte vérifié de ce qui est là » (BMAD),
   « comportement actuel / attendu / inchangé » (Kiro, fiche correctif). Notre `etat-des-lieux.md` en est l'équivalent.
6. Aucune source lue ne DÉTECTE automatiquement neuf/existant : c'est l'humain qui choisit son point d'entrée (BMAD, Kiro).
   La détection de L5 est donc à inventer, avec des signaux que nous avons (CODEMAP, routes, prod).
7. Les relecteurs-agents sont peu précis quand ils lisent un diff : 56,3 % de leurs commentaires rejetés (CodeRabbit, 31 073
   paires, préimpression de juillet 2026). Mesurer le taux de constats CONFIRMÉS par tour est un manque de la rétro.
8. Plus d'agents ≠ plus vite : chez Cursor, 20 agents à verrous « se comportaient comme 2 ou 3 » ; Huntley refuse le multi-agent.
   Notre §6.2 (coutures entre lanes) va dans le même sens.
9. La mesure perçue est trompeuse : l'essai METR mesure +19 % de temps avec l'IA alors que les développeurs croient −20 %
   (juillet 2025, vieux). Argument pour des critères de sortie objectifs (rétro §6.6).
10. Beaucoup de chiffres « miracle » sont des assertions de promoteurs (12 h → 15 min ; 297 $ pour un contrat de 50 k$) : à ne pas reprendre.

## 2. Pratiques à adopter
| Pratique | Source (lu / mémoire) | Mécanisme précis | Ce qu'elle aurait changé le 19-20/11 | Coût | Niveau |
|---|---|---|---|---|---|
| Disjoncteur par constat : 5 tours max, tours 1-3 par le même implémenteur, 4-5 par un frais et plus fort, re-revue « scopée » ADDRESSED / NOT ADDRESSED sur le seul diff du correctif | Superpowers, `skills/subagent-driven-development/SKILL.md` et `references/fix-loop.md` sur `main` (lu, sans date) | Une ligne de journal par tour ; mineurs « différés » sans entrer dans la boucle ; à 5 tours, l'orchestrateur tranche : « parqué avec décision » ou « plus petit changement qui débloque » ; jamais de rejet silencieux | §4 : ≈ 25 % de corrections « faites et prouvées » réglées à moitié, 3 puis 2 régressions : un tour de contre-vérification SCOPÉ par correctif, borné, aurait cadré le coût (§6.7) | faible (règle + journal) | L4, L5 |
| Registre machine à état : une ligne par constat/tâche avec `passes` (faux/vrai) + fichier de notes ajoutées seulement | Ralph de snarktank, `prd.json` + `progress.txt` (lu, GitHub) ; Kiro `tasks.md` à état (lu) ; Codex `Documentation.md` (lu) | La boucle ne lit que l'état + le git ; la sortie = tous à vrai OU plafond d'itérations | §6.8 (l'orchestrateur est le goulot, rapports en prose) et §8 (registre) : le registre devient la seule chose que l'orchestrateur relit | faible | L4 |
| Quatre fichiers par chantier : cible figée (buts, NON-buts, contraintes, « done when », démonstration) / plan à jalons avec commandes de validation + règle « stop-and-fix » / mode d'emploi (« diffs bornés, pas d'extension de périmètre ») / journal (état, décisions, problèmes connus) | OpenAI, « Run long horizon tasks with Codex » (lu, sans date, GPT-5.3-Codex ; 25 h, ≈ 13 M tokens, ≈ 30 k lignes, « une expérience, pas une prod ») | Les « done when » sont écrits AVANT ; chaque jalon tient dans une boucle | §6.5 (cibles jamais atteintes faute de critère décidé au début) : le « done when » chiffré du tour 0 | faible | L4 (existant), L5 (neuf) |
| Étape « composer » obligatoire : après chaque tâche, écrire la règle apprise ET demander « le système l'attraperait-il tout seul la prochaine fois ? » (test, lint, agent de revue) | Every, guide « Compound Engineering » (lu, sans date, vers fin 2025 par inférence) ; plugin `EveryInc/compound-engineering-plugin` : `/ce-compound`, `docs/solutions/` (lu) | Les leçons vont dans `CLAUDE.md`/`AGENTS.md`, `docs/solutions/` (YAML pour retrouver), `todos/` P1-P3 | §6.1 (la même classe revenue 4 fois) et §8 (classes → gardes permanentes) : la question force la garde au lieu de la prose | moyen (écrire la garde) | L4, L5 |
| Une carte courte (≈ 100 lignes) qui POINTE vers `docs/`, des règles d'architecture imposées par tests structurels, et un « ramasse-miettes » récurrent de la qualité | OpenAI « harness engineering », 11/02/2026 : lu seulement via InfoQ du 21/02/2026 et un résumé de recherche (le billet : 403) | Cinq mois, ≈ 1 M de lignes sans code écrit à la main (chiffres du billet via tiers, non vérifiés) ; liens croisés validés par lint/CI | §6.1/§6.8 ; chez nous `CLAUDE.md` est déjà énorme : le contraire de la carte courte | moyen | L5 |
| Journal de décisions de l'orchestrateur : « ce que j'ai décidé, pourquoi, coût si j'ai tort », au lieu de poser une question | Superpowers (lu) ; Codex `Decision notes` (lu) | Arrêt humain seulement pour : irréversible, sécurité, effet hors worktree (merge, push partagé), plan cassé | §5.8 déjà fait (choix tranchés par règle) ; ajoute le « coût si faux » pour rendre la décision réversible | faible | L4 |
| Tâche taillée pour UNE fenêtre de contexte (ex. une colonne + sa migration ; pas « tout le tableau de bord ») ; `Implement` borne les diffs | snarktank/ralph (lu) ; Huntley 14/07/2025 : une chose par boucle, ≈ 170 k tokens utiles (lu) | Découper avant d'envoyer ; une lane trop grosse = mauvais code quand le contexte s'épuise | §6.7 (lanes à 500-800 k tokens) | faible | L4, L5 |
| Mesurer le TAUX DE CONSTATS CONFIRMÉS (acceptés/discutés/rejetés) par relecteur et par axe, pas le volume | agentpatterns.ai citant l'arXiv 2607.03316 (lu en secondaire) ; l'arXiv lui-même (lu) | Pré-filtrer la validité avant d'envoyer ; les constats « évolutivité » sont plus invalides que les fonctionnels | §3 : on compte 152/78/30 constats mais pas combien la consolidation a écartés ; ce taux dit si un axe de relecteur vaut son prix | faible | L4 |
| Chemin « correctif/existant » distinct : fiche « comportement actuel / attendu / INCHANGÉ » + régression, sans les trois portes du neuf ; « Quick Spec » sans porte pour le bien compris | Kiro docs « Specs » (lu) | Un correctif porte l'inchangé noir sur blanc (= nos régressions) | §4 : les 3 puis 2 régressions viennent de l'inchangé non écrit | faible | L5 |

## 3. Pièges et contre-indications
- **Spec lourde = surcoût (Böckeler, martinfowler.com, 15/10/2025, outils testés en sept. 2025, lu).** Kiro : un petit bug devenu 4 récits et
  16 critères ; Spec Kit plus long que coder directement pour une tâche de 3-5 points ; elle préfère relire du code que de
  nombreux fichiers markdown répétitifs ; l'agent de Spec Kit a ignoré des classes existantes et créé des doublons, et sur-appliqué
  un article de la constitution ; adopter ces outils sur l'existant est plus dur. À date : l'outil a pu changer.
- **Spec Kit : zéro preuve (lu, `spec-driven.md`).** « 12 h → 15 min » sans méthode ; « les specs restent synchronisées parce qu'elles
  génèrent le code » est une intention. Les listes « tests unitaires de l'anglais » sont une auto-relecture par le LLM, sans mesure.
- **Ralph n'est pas pour l'existant (Huntley, 14/07/2025, lu).** « Greenfield, 90 % faits » ; il dit qu'il ne l'utiliserait pas sur du code
  existant. Modes d'échec : la recherche conclut « absent » alors que ça existe (→ doublon), implémentations en double,
  « placeholders », mauvaise spec (un mot-clé défini deux fois a coûté cher). Il n'y a PAS de règle d'arrêt dans sa boucle :
  l'arrêt est humain (il « regarde la boucle », `git reset --hard`). Son billet du 17/01/2026 (lu) refuse le multi-agent
  (« microservices non déterministes ») et ne dit rien sur l'existant.
- **Cursor, « Scaling long-running autonomous coding » (W. Lin, 14/01/2026, lu).** Agents à verrous : 20 agents = 2-3 ; sans hiérarchie ils
  évitent le dur et tournent en rond ; un rôle d'intégrateur dédié a créé des goulots, donc supprimé (les workers règlent
  leurs conflits) ; dérive et vision tunnel exigent des redémarrages à neuf périodiques ; la migration Solid→React (+266 k/−193 k) passe la CI
  mais « demande encore une revue soigneuse ». Aucun coût en dollars, aucun critère d'arrêt (seul un « juge » décide de continuer à chaque cycle).
  Opus 4.5 « s'arrêtait tôt et prenait des raccourcis » — propre à ce modèle à cette date, à ne pas généraliser.
- **Revue par agent : précision faible, et un benchmark partisan.** CodeRabbit en production : 36,4 % acceptés, 7,3 % discutés,
  56,3 % rejetés (31 073 paires, 10 191 PR, 239 dépôts ; arXiv 2607.03316, préimpression, non relue par des pairs, lu).
  Le « benchmark » `greptile.com/benchmarks` (juillet 2025, 50 bugs, lu) donne Greptile 82 %, Bugbot 58 %, Copilot 54 %,
  CodeRabbit 44 %, Graphite 6 % : page sans auteur nommé, hébergée par une organisation `ai-code-review-evaluation`, Greptile en tête partout,
  aucun chiffre de faux positifs malgré ce que la page dit mesurer, et son propre total Copilot ne se recoupe pas (26/50 = 52 %, pas 54 %). À ne pas citer comme vérité.
- **Les agents produisent plus de défauts qu'un humain, selon un VENDEUR de revue.** CodeRabbit, 17/12/2025 (lu) : 470 PR, 10,83 vs 6,45 problèmes
  par PR, logique +75 %, lisibilité ×3, sécurité jusqu'à ×2,74 ; l'étiquette « humain » est déduite, la source vend de la revue. Direction plausible, chiffres à prendre avec prudence.
- **METR (arXiv 2507.09089, 12/07/2025, lu).** 16 développeurs expérimentés, 246 tâches, projets matures : +19 % de temps avec l'IA ;
  ils prévoyaient −24 % et estimaient −20 % après coup. Outils de début 2025 (Cursor Pro, Claude 3.5/3.7) : probablement dépassé, mais le
  décalage perçu/mesuré est le message utile.
- **Assertions de promoteurs.** Every : « 95 % de déchet à la première tentative, 50 % à la seconde », « 1 h pour un agent de revue économise 10 h », sans donnée (lu,
  la page se dit elle-même anecdotique) ; Huntley : un contrat de 50 k$ livré pour 297 $ de tokens (iMessage partagé) ; Devin « 67 % de PR fusionnées, contre 34 % »
  n'est lu qu'en secondaire (la page Cognition n'a pas pu être lue) et un commentateur note que l'entonnoir tâches → PR n'est pas publié.
- **Contradiction n°1 (la plus sérieuse).** La rétro (§3, §4) traite les constats des relecteurs comme la mesure du niveau, et les corrections
  « réglées » comme un acquis ; or les relecteurs-agents rejetés à 56 % sur diff montrent qu'un constat sans preuve n'est pas un fait. Notre méthode
  s'en protège par la PREUVE (gestes + capture) et la vérification contre le code à la consolidation, mais le TAUX de constats écartés n'est enregistré nulle part :
  on ne sait pas si un axe ou un relecteur produit surtout du bruit. À corriger dans L4 (champ `verdict_consolidation` dans le registre).
- **Contradiction n°2.** Cursor a SUPPRIMÉ l'intégrateur parce qu'il goulottait ; la rétro §6.8 propose un « agent plieur ». Échelles différentes
  (centaines de workers vs ≈ 8 lanes), donc pas tranché : tester le plieur sur une vague avant d'en faire une règle.
- **Contradiction n°3.** Every dit 80 % de l'effort en plan + revue, 20 % en exécution (puis 50/50 avec l'amélioration du système) ; la rétro, sur l'existant, a mis l'effort dans la revue sur écran réel et presque rien dans le plan.
  Pas une erreur : l'existant n'a pas besoin du plan, mais le « composer » d'Every (règle apprise → garde) nous manque.

## 4. Neuf ou existant
- **Sources centrées sur le neuf :** Ralph (greenfield, Huntley) ; Codex long-horizon (dépôt vide) ; Spec Kit / Kiro / BMAD (parcours « nouvelle fonction » par défaut).
- **Sources qui traitent l'existant :**
  - BMAD v7 (docs, lu ; version stable 6.12, v7 en alpha, « attendue mi-novembre 2026 ») : « point d'entrée selon ce que vous avez » (rien / un changement tenant en une session /
    une grande idée / du code existant sans décisions écrites / un prototype à industrialiser) ; pour l'hérité : « établir un contexte vérifié et travailler à partir de ce qui est réellement là » ;
    **« le grand travail entre plus tôt dans la boucle et la parcourt plus souvent ; ce n'est pas un autre processus »**. Les guides brownfield n'ont pas été lus ; les rôles (analyste, PM, architecte, scrum master, dev, QA) et les niveaux de planification de la v6
    ne sont PAS dans les pages lues : mémoire seulement.
  - Kiro : fiche correctif (actuel / attendu / inchangé) ; fichiers « steering » `product.md`, `tech.md`, `structure.md` générables, chargés toujours ou par motif de fichier ou à la demande (lu). Comment Kiro traite l'existant n'est pas décrit.
  - Spec Kit : lien vers un guide « projets existants » (404 sur le chemin tenté, non lu) ; Böckeler dit que l'étape de recherche aidait sur l'existant mais que l'agent ne s'en servait pas toujours.
  - snarktank/ralph : s'installe dans un dépôt existant (`scripts/ralph/`), exige des conventions du dépôt dans le prompt (lu).
- **Détection :** AUCUNE source lue ne détecte seule le cas. BMAD et Kiro laissent l'humain choisir (ou lui donnent un menu « ce que vous avez »). Signaux utilisables chez nous (venant de la rétro §8, non des sources) : dans CODEMAP, routes, données en prod, tâches cochées, verbe de la demande.
- **Le piège commun du neuf vs existant** (Huntley, Böckeler) : sur l'existant, l'agent ne retrouve pas ce qui est déjà là et le recrée. D'où : première étape de l'existant = inventaire vérifié AVANT toute écriture, et une règle « ne pas supposer qu'il manque » dans le brief des lanes de correction.
- **Quand la demande est vague :** BMAD fait « clarifier » d'abord ; Spec Kit marque `[NEEDS CLARIFICATION]` dans la spec (lu) ; Kiro « Analyze Requirements » avant la conception (lu). Chez nous, « aucune question » du fondateur exige de remplacer la question par une décision écrite + son coût si faux.

## 5. Critères de sortie et mesures
- Ralph (snarktank) : toutes les histoires `passes: true`, OU 10 itérations (réglable) ; typecheck + tests avant chaque commit ; CI verte ; histoires UI « vérifier dans le navigateur » (lu).
- Codex : « done when » + démonstration dans la cible figée ; validations par jalon ; stop-and-fix (lu). Pas de mesure de qualité, seulement « réel et testable, pas prêt pour la prod ».
- Superpowers : revue propre, ou tous les points ouverts « parqués avec décision » après 5 tours (lu).
- Spec Kit : répéter implémenter + `converge` « jusqu'à `Converged` » (lu, mécanisme non décrit). Kiro : aucun critère de vérification décrit.
- Cursor : un juge continue/arrête à chaque cycle ; pas de critère publié. Huntley : jugement humain.
- Revue de code : taux d'acceptation (CodeRabbit 36,4 %) ; aucune source ne fixe un seuil de « tour sec ». **Notre « dry-cap » de L3 (2 tours à vide) et la courbe 152 → 78 → 30 → 2 n'ont pas d'équivalent publié** : c'est de l'original, à garder, mais à doubler d'un plafond dur.
- Mesures utilisables : durée (Codex 25 h), tokens (≈ 13 M), lignes (≈ 30 k) pour un cadrage de coût ; taux de fusion (Devin, secondaire) ; METR rappelle de ne pas se fier au ressenti.

## 6. Non couvert, non trouvé, douteux
- Billet OpenAI « harness engineering » (11/02/2026) : 403, lu seulement via InfoQ + un résumé de recherche ; le « ramasse-miettes » et ses chiffres de PR (≈ 1 500) sont secondaires. Billet Cognition (Devin) : DNS impossible ; 67 %/34 % secondaire.
- BMAD : rôles et parcours brownfield non lus (la doc v7 est un autre découpage) ; DORA 2025 : une phrase lue (« l'IA amplifie »), aucun chiffre ; Spec Kit clarify/analyze/existant non lus.
- Non trouvé : revue multi-agents publiée avec taux de vrais positifs HORS vendeurs (seule l'étude Monash/Melbourne de CodeRabbit) ; retours d'équipes chiffrés sur la dérive et la dette à 6-12 mois ; tout critère de sortie « tour sec » ; toute détection auto neuf/existant.
- La question « qui vérifie, avec quoi » pour un fondateur non-codeur n'est traitée par aucune source (toutes supposent un développeur qui relit).
- Sources de tiers (agentpatterns.ai : 16,6 % vs 56,5 % d'adoption IA vs humain, 12 agents sur 13 sous 60 % d'actionnable) : chiffres NON vérifiés dans les arXiv cités.

## 7. URL des sources lues
- Huntley : https://ghuntley.com/ralph/ (14/07/2025) ; https://ghuntley.com/loop/ (17/01/2026) — snarktank : https://github.com/snarktank/ralph
- Böckeler : https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html (15/10/2025)
- Spec Kit : https://github.com/github/spec-kit/blob/main/spec-driven.md et https://github.com/github/spec-kit ; Kiro : https://kiro.dev/docs/specs/ et https://kiro.dev/docs/steering/
- BMAD : https://github.com/bmad-code-org/BMAD-METHOD et https://docs.bmad-method.org/
- Superpowers : https://github.com/obra/superpowers ; raw.githubusercontent.com/obra/superpowers/main/skills/subagent-driven-development/SKILL.md et .../references/fix-loop.md
- Every : https://every.to/guides/compound-engineering ; https://github.com/EveryInc/compound-engineering-plugin
- Cursor : https://cursor.com/blog/scaling-agents (14/01/2026) ; OpenAI Codex : https://developers.openai.com/blog/run-long-horizon-tasks-with-codex ; InfoQ : https://www.infoq.com/news/2026/02/openai-harness-engineering-codex
- Revue : https://arxiv.org/abs/2607.03316 ; https://agentpatterns.ai/code-review/agentic-review-comment-acceptance/ ; https://www.greptile.com/benchmarks ; https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report
- METR : https://arxiv.org/abs/2507.09089 ; DORA : https://dora.dev/research/2025/dora-report/
