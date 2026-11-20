# Lane A-anthropic — ce qu'Anthropic publie sur les longues tâches multi-agents (recherche du 20/11/2026)

Méthode : 1 WebSearch + 13 WebFetch de pages entières (budget respecté). « lu » = lu cette session via WebFetch (le
résumé vient d'un petit modèle d'extraction : les chiffres sont ceux de la page, les citations ne sont pas mot pour mot).
Rien « de mémoire » n'entre dans ce rapport. Les docs en ligne (code.claude.com, platform.claude.com) ne portent pas de
date : elles sont « vivantes » au 20/11/2026 et citent Fable 5.2 / Opus 5.5 ; les billets d'ingénierie sont datés ci-dessous.

Sources (toutes lues) : [MA] anthropic.com/engineering/multi-agent-research-system (13/06/2025) · [BEA]
…/building-effective-agents (19/12/2024, la page dit elle-même que l'outillage a changé) · [HAR] …/effective-harnesses-for-
long-running-agents (26/11/2025) · [CTX] …/effective-context-engineering-for-ai-agents (29/09/2025) · [EVAL]
…/demystifying-evals-for-ai-agents (09/01/2026) · [HD] …/harness-design-long-running-apps (24/03/2026, Prithvi
Rajasekaran, Labs) · [CC] …/building-c-compiler (05/02/2026, N. Carlini) · [BP] code.claude.com/docs/en/best-practices ·
[AT] code.claude.com/docs/en/agent-teams · [CR] code.claude.com/docs/en/code-review-local · [PB]
platform.claude.com/…/claude-prompting-best-practices · [F5] …/prompting-claude-fable-5 · [F52] …/prompting-claude-fable-5-2.

## 1. L'essentiel en dix lignes
1. Ce que nous avons fait le 19-20/11 (relecteurs NEUFS sur l'écran RÉEL, contre-vérification par d'autres neufs) est
   exactement ce qu'Anthropic recommande : un évaluateur séparé est « bien plus facile à rendre sceptique qu'un générateur
   à rendre critique de son propre travail » [HD] ; « des vérificateurs en contexte neuf battent l'autocritique » [F5].
2. Anthropic confirme notre chiffre (≈ 25 % des corrections « prouvées » à moitié réglées) : l'auteur se flatte [HD].
3. Mais ils disent aussi : un évaluateur n'a de valeur que si la tâche dépasse ce que le modèle fait seul ; sur Opus 4.6
   l'évaluateur « devenait un surcoût » pour ce qui est à portée solo [HD]. L4 doit se dimensionner sur le modèle ET la tâche.
4. Le levier n°1 de qualité d'un travail long est un **fichier d'état de données** (liste de fonctions JSON, champ
   `passes` seul modifiable, progression, git) [HAR] : c'est notre idée « registre des constats » (rétro §8), validée.
5. Le levier n°2 est un **contrat de sortie convenu AVANT de construire** (« sprint contract », 27 critères pour un seul
   sprint) [HD] et un **vérificateur quasi parfait** : sinon l'agent résout le mauvais problème [CC]. = nos critères chiffrés du tour 0.
6. Arrêt : jamais « boucle jusqu'à fini » dans le prompt ; une condition vérifiable par la machine (`/goal` jugé par un
   second modèle, hook `Stop` plafonné à 8 blocages, `--max-turns`, `--max-budget-usd`) [BP].
7. Un relecteur à qui on demande des défauts en trouve toujours : il faut dire « ignore le style » et trier [BP] — ce qui
   explique la courbe qui ne tombe pas à zéro (rétro §3) : arrêter sur une règle, pas sur un tour sec.
8. Le coût domine : l'usage de jetons explique 80 % de la variance de performance [MA] ; multi-agents ≈ 15× un chat ;
   harnais complet 20× un agent seul (6 h, 200 $ contre 20 min, 9 $) [HD]. Dimensionner : 3-5 agents, pas 8-16 [MA][AT].
9. Contradiction sérieuse avec la maison : Anthropic dit de garder CLAUDE.md court, de transformer les règles absolues en
   hooks, de retirer les consignes « délègue toujours » ; notre CLAUDE.md fait l'inverse (§3).
10. Rien trouvé sur la détection automatique neuf / existant : on a des briques (§4) mais la détection reste à inventer.

## 2. Pratiques à adopter
| Pratique | Source (lu) | Mécanisme précis | Ce que ça aurait changé (rétro §) | Coût | Niveau |
|---|---|---|---|---|---|
| Registre de constats en JSON, un seul champ d'état modifiable | [HAR] | Liste (> 200 entrées) `{catégorie, description, étapes, passes}`, tous « en échec » au départ ; l'agent ne change que `passes` ; « retirer ou éditer un test est inacceptable » ; JSON choisi car le modèle l'écrase moins que du Markdown | §6.8 (orchestrateur noyé de prose), §8 idée 1 : rapports courts + id/état/preuve | faible (un fichier) | L4+L5 |
| Contrat de sortie négocié avant la correction | [HD] | Le générateur propose ce qu'il fera et comment ce sera vérifié ; l'évaluateur relit jusqu'à accord ; critères granulaires ; seuil dur PAR critère (un seul sous le seuil = échec) | §6.5 (mesures cibles jamais atteintes), §6.6 (pas de note objective) | moyen (un aller-retour par lane) | L4+L5 |
| Évaluateur étalonné par exemples à notes détaillées | [HD] | Few-shot avec décomposition des notes ; critères pondérés (beauté/originalité plus que fonction) ; Playwright sur l'app vivante, captures, critique écrite | §6.6 : notes /10 par écran contre une référence nommée dès le tour 1 | moyen | L4+L5 |
| Vérification par intervalles PENDANT la construction | [F5] | « Établis une méthode de contrôle à intervalle X ; exécute-la tous les X en vérifiant avec des sous-agents contre la spécification » | §4 : 25 % de « à moitié » attrapés seulement au tour suivant ; on attrape à la fin de la lane | moyen | L5 (L4 optionnel) |
| Bloc d'ancrage dans tout prompt d'agent | [F5] | « Avant de rapporter, audite chaque affirmation contre un résultat d'outil… » : « a presque éliminé » les faux rapports d'avancement | déjà dans CLAUDE.md ; garder, ne pas diluer | nul | tous |
| Critique à rôle spécialisé en fin de vague | [CC] | Agents dédiés : dédoublonnage, qualité, critique de conception, doc | §6.1 : classe de défaut revenue 4× ; un agent « classe d'invariant » | moyen | L5 |
| Sondes rapides à échantillon + sortie courte | [CC] | `--fast` (1 % / 10 % déterministe par agent), journaux dans fichiers, erreurs taguées `ERROR`, stats pré-calculées | §6.7 (captures relues, journaux CI) ; renforce l'éclaireur haiku | faible | L4+L5 |
| CI qui bloque les régressions + oracle connu | [CC] | CI ajoutée quand l'agent « casse l'existant » ; GCC comme oracle pour découper une tâche monolithique | §4 (3 puis 2 régressions) : garde de non-régression dès le tour 1 | moyen | L4+L5 |
| « Prendre ses repères » avant toute vague | [HAR] | `pwd`, journal git, fichier de progression, liste de fonctions, démarrer le serveur par `init.sh`, test bout-en-bout de base AVANT de coder | §6.4 (poste ≠ CI), pile jetable ; ETAT.md déjà là | faible | L4+L5 |
| Évaluations tirées des échecs réels, lues en transcriptions | [EVAL] | 20-50 tâches issues d'échecs ; évals « capacité » (taux bas) qui « gradue » en « régression » (~100 %) ; lire les transcriptions ; jeux équilibrés (doit / ne doit pas) ; essais isolés | rétro §8 idées 3-4 : classes de défauts → gardes ; gestes des relecteurs → specs | moyen | L5 |
| Juge LLM étalonné sur humain, mono-appel | [MA][EVAL] | Rubrique unique, un appel, note 0-1 + passe/échoue ; étalonner sur des humains ; garder un testeur humain (il a vu ce que l'auto a raté) | l'étage « vraie vie » manquant (§6.9) | faible | L5 |
| `pass^k` pour la constance | [EVAL] | P(k essais tous réussis) : 75 % par essai → ≈ 42 % sur 3 | test « instable » = vrai défaut (§4) : rejouer k fois les parcours critiques | moyen | L5 |
| Revue contre spécification, « ignore le style » | [BP] | `use a subagent to review … against SPEC.md … report gaps that affect correctness and skip style` | gravité A/B/C déjà ; garder la clause « skip style » | nul | L4+L5 |
| Hook `Stop` / `/goal` pour les runs sans témoin | [BP] | Hook exit 2 renvoie l'agent au travail ; plafond de 8 blocages sans appel d'outil ; `/goal` = un second modèle vérifie la condition à chaque tour | une lane qui rend « fini » avec des items ouverts | faible | L5 |
| Questions avant de lâcher un run | [BP] | 5 questions : sait-il ce qu'est « fini » ? peut-il se vérifier ? que peut-il toucher ? qu'est-ce qui l'arrête ? qui valide ? | formalise nos « conditions d'emploi » (rétro §7) | nul | L4+L5 |

## 3. Pièges et contre-indications (dit sans ménagement)
- **CLAUDE.md trop lourd, règles absolues, consignes de déléguer.** [BP] : « Keep CLAUDE.md short », ce qui est
  obligatoire devient hook/règle de refus, ce qui ne se déduit pas du dépôt seul est écrit ; empiler IMPORTANT/NEVER fait
  sur-appliquer la règle. [F52] : les « never » sont lus comme absolus ; les prudences s'accumulent (mémoire, notes) et
  bloquent le travail autonome, surtout « quand plusieurs agents travaillent ensemble » ; solution : retirer, nommer les
  pas SANS approbation, repartir d'une mémoire élaguée. [F52] : relire les lignes « délègue » des prompts/skills. Notre
  CLAUDE.md (749 lignes mesurées au `wc -l`, « EVERY-PROMPT RULE » qui force la délégation, règles « jamais ») est exactement le profil visé.
  À argumenter avant de l'accepter : nos règles #1-#5 sont des invariants — [BP] dirait « hooks », ce que la maison fait
  déjà pour une part (CI `check_stages`, import-linter). Ce qui reste en prose devrait y passer.
- **Déléguer ne rend pas la réponse meilleure** [BP] ; seul un relecteur neuf aide « parce qu'il n'a pas vu votre
  raisonnement ». Notre règle « délègue le volume mécanique » est défendable (parallélisme, sortie bruyante) mais pas
  comme gain de qualité ; [BP] : un sous-agent frais peut être PLUS LENT que de faire sur place.
- **Les agents multiples sont un mauvais choix pour la plupart des tâches de code** (peu de sous-tâches parallélisables,
  contexte partagé) [MA 06/2025 — ancien]. Nuancé depuis : [F5] « beaucoup plus fiable pour lancer et tenir des sous-agents
  parallèles » ; [AT] : bon pour revue, modules neufs, hypothèses concurrentes ; mauvais pour fichiers communs.
  Nos lanes disjointes en fichiers suivent [AT], mais le rétro §6.2 montre qu'elles se touchent en COMPORTEMENT :
  Anthropic ne règle pas ça non plus ([AT] : « chaque coéquipier possède d'autres fichiers » c'est tout).
- **Sur-recrutement** : [MA] 50 sous-agents pour une question simple ; règles de dosage dans le prompt (1 agent /
  3-10 appels ; 2-4 sous-agents / 10-15 appels ; > 10 pour le complexe). [AT] : 3-5 coéquipiers, « trois ciblés valent
  mieux que cinq dispersés », 5-6 tâches chacun. Nous : 8 lanes + 4-6 relecteurs par tour = au-delà de leur zone.
- **Un évaluateur sort complaisant** : il trouve de vrais défauts puis « se convainc d'approuver » et teste en surface [HD].
  Parade chez eux : étalonner par exemples + seuils durs ; chez nous : preuve exigée (gestes + capture) — plus strict, OK.
- **Un relecteur trouve toujours quelque chose** [BP] : corriger tout → couches d'abstraction et tests de cas impossibles.
  Triage déjà fait chez nous (« avant le merge » / « peut attendre »). Renforce : ne jamais viser « tour sec ».
- **L'auteur s'auto-déclare fini / marque « passe » sans test** [HAR] (parade : liste de fonctions qui borne la portée +
  test bout-en-bout navigateur ; l'état « passes » seul modifiable). Les tests unitaires + `curl` ratent le bout-en-bout ;
  limites : les `alert` natifs invisibles [HAR]. Cf. notre « jamais attrapé : vrai iPhone / Safari ».
- **Passer les tests ≠ fini** [CC] ; code qui « fait passer » au lieu de résoudre : [PB] « Avoid focusing on passing tests
  and hardcoding » (lu en titre ; contenu non relu en détail). [EVAL] : noter le RÉSULTAT, pas le chemin ; isoler les essais
  (un agent a lu l'historique git des essais précédents).
- **Ne pas afficher de budget de jetons / compte à rebours au modèle** [F5][F52] : provoque « proposer une nouvelle
  session » ; retirer un gros budget affiché a baissé le coût à performance égale [F52 : ce n'est pas le « task budget » API].
- **« Continue / ne sois pas paresseux »** : plutôt cause de sur-travail ; donner un contrôle à passer [BP].
- **Phrase « tu es le propriétaire du code »** [F52] : consolide 75 % du temps (contre < 10 %) mais +70-80 % de jetons,
  changements non demandés, résumé de PR incomplet ; et une règle « pas de refactor » ne l'annule pas.
- **Contexte** : 200 000 jetons tronquent [MA] ; « context rot » [CTX] ; contre-vérifier seul ne protège pas
  l'orchestrateur — c'est notre goulot (§6.8). Parade [CTX][MA] : sous-agent renvoie 1 000-2 000 jetons ; sorties écrites
  dans un système de fichiers, références légères renvoyées ; plan sauvé en mémoire externe avant dépassement.
- **L'harnais vieillit** [HD] : « chaque composant encode une hypothèse sur ce que le modèle ne sait pas faire » ; retirer
  UN composant à la fois (une coupe radicale a échoué sans dire quoi portait la charge). Le sprint a été retiré avec Opus 4.6,
  le planificateur gardé, l'évaluateur passé en une passe finale. → L4/L5 doivent porter une date de modèle et se revalider.

## 4. Neuf ou existant
- **Anthropic n'a pas de détecteur** neuf/existant : non trouvé. Ce qui suit est lu, la mise en regard est notre inférence.
- **Neuf** : phase d'initialisation une fois (spec produit, liste de fonctions, `init.sh`, premier commit) puis sessions
  incrémentales à une fonction [HAR] ; un **planificateur** est gardé même sur modèles récents, sinon l'agent sous-dimensionne
  [HD] ; interroger l'humain jusqu'à pouvoir écrire `SPEC.md`, puis session fraîche pour construire [BP] ; « sois ambitieux »
  (cas limites, états vides) car le modèle lit la demande a minima [BP].
- **Existant** : « prendre ses repères » et un test bout-en-bout de base AVANT d'ajouter [HAR] ; ne documenter que ce que le
  code ne dit pas, y compris les endroits où le code trompe (ancien motif partout à ne pas copier) [BP] ; reproduire par un
  test rouge d'abord [BP] ; évaluateur sur l'app vivante [HD] ; contrat de non-régression en CI [CC].
- **Variable décisive trouvée** : la propriété du code [F52]. Sans mention, le modèle AJOUTE à la structure existante, même
  en dupliquant ; avec « tu es le mainteneur », il consolide (+ jetons, + changements non demandés). Donc L4/L5 doivent dire
  explicitement, dans le brief de lane, « améliorer sans toucher au reste » ou « tu possèdes ce module ».
- **Signaux de détection plausibles** (mes inférences, à tester) : le module existe-t-il dans la CODEMAP, a-t-il des routes,
  des écrans, des données en prod, des tâches cochées ; mot de la demande build / improve / review / redo. Anthropic ne
  fournit pas de seuils. Un cas mixte (le typique : écran existant + fonction neuve) est à traiter par lane, pas globalement.

## 5. Critères de sortie et mesures
- Toujours **une condition vérifiable**, pas un sentiment : test, code retour de build, linter, diff contre une référence,
  capture à côté de la maquette [BP] ; évidence demandée (« la commande et sa sortie, ou la capture ») [BP].
- Contrôles de la machine : `/goal` (second modèle juge à chaque tour) ; hook `Stop` (exit 2, plafond 8 blocages de suite) ;
  `--max-turns` / `--max-budget-usd` ; branche protégée + humain qui approuve le merge [BP]. Boucles itératives : nombre
  maximal d'itérations [BEA].
- Évaluateur-optimiseur : à utiliser seulement si les critères sont clairs et si l'itération améliore mesurablement [BEA].
  Chez eux : 5 à 15 itérations ; seuil dur par critère ; QA ~7-10 min contre construction 1-2 h (QA 3,24 $ / 3,09 $ / 4,06 $
  sur 124,70 $ au total) [HD] → la vérification est bon marché RELATIVEMENT à la construction.
- Saturation : une éval que l'agent réussit entièrement ne donne plus de signal ; viser des évals « capacité » à taux bas
  et basculer en « régression » à ~100 % [EVAL]. Aucun chiffre Anthropic du type « N tours sans nouveau constat ».
- **Non trouvé** : règle d'arrêt chiffrée pour des tours de revue. Notre « avant le merge seulement » + 2 bloquants est
  plus précis que ce qu'ils publient ; le seul garde-fou externe pertinent : arrêter quand le coût marginal dépasse la
  valeur (`/usage`, [BP]) et quand les constats restants relèvent de « style ».
- Mesures utiles reprises de [EVAL] : taux de passage par critère, `pass^k`, lecture d'échantillons de transcriptions
  (« les échecs doivent sembler justes »).

## 6. Tenue d'une tâche de plusieurs heures ou jours
- Fichiers d'état : progression en texte libre + état structuré en JSON + git comme journal et points de reprise [PB][HAR].
  Notre `ETAT.md` + `vague*.md` en sont l'équivalent ; manque la partie JSON (registre).
- Réinitialisation vs compaction : sur Sonnet 4.5, la « anxiété de contexte » rendait la compaction insuffisante, la remise
  à zéro + passation structurée est devenue essentielle ; Opus 4.5/4.6 l'ont supprimée, compaction automatique suffit [HD].
  Sur Fable : ne pas montrer de compte à rebours de contexte [F5]. Conclusion : on peut garder des passations simples, mais
  l'orchestrateur long (le nôtre était à 90 %) gagne à écrire un plan en mémoire externe tôt [MA].
- Notes structurées hors contexte (NOTES.md/liste de tâches) pour le travail itératif à jalons ; sous-agents pour l'exploration
  parallèle ; compaction pour le va-et-vient [CTX]. Mémoire Fable : un fichier par leçon, une ligne de résumé, corriger plutôt
  que dupliquer, supprimer les notes fausses [F5] — proche de nos règles anti-gonflement.
- Reprise : agents reprenant au point d'erreur, points de contrôle réguliers [MA] ; sessions nommées/reprises [BP].
- Runs longs : vérifier de façon ASYNCHRONE (jobs planifiés) plutôt que bloquer [F5] ; sous-agents longue durée qui gardent
  leur contexte économisent du cache (lectures) [F5] — à rapprocher de notre règle « reprendre un agent seulement pour
  approfondir sa lane ».

## 7. Ce qui, dans la rétro de la maison, dépasse ou contredit Anthropic
- **Dépasse** : la contre-vérification systématique de CHAQUE correction par un neuf (25 % à moitié) ; la preuve gestes +
  capture ; l'appareil « classe de défaut → invariant » ; la lane de couture seule sur l'arbre ; la consolidation qui
  vérifie contre le code ; l'éclaireur haiku pour les journaux CI. Anthropic n'a rien d'équivalent publié (non trouvé).
- **Contredit / à réexaminer** : (a) volume de relecteurs opus à effort high × 16 : [F52] dit `high` est le défaut à la
  capacité utile, `xhigh` seulement si gain mesuré, et `medium` là où les évals tiennent ; [F52] `low` est « intelligent et
  rapide » pour sous-agents en volume — des éclaireurs/consolidateurs pourraient descendre ; (b) le rétro n'a pas mesuré
  « le tour N+1 ajoute-t-il de la valeur ? » — [HD] pose la question explicitement pour chaque composant ; (c) CLAUDE.md (§3) ;
  (d) 8 lanes au lieu de 3-5 [AT] — justifiable par les fichiers disjoints, pas par une recommandation.
- **Non couvert chez Anthropic mais décisif ici** : vrai appareil / une semaine d'usage ; Anthropic confirme seulement que la
  vision/navigateur automatisé a des limites [HAR] et qu'un testeur humain voit ce que l'auto rate [MA].

## 8. Non couvert, non trouvé, douteux
- Non lu : docs sous-agents, workflows, skills, hooks, mémoire (pages de référence), « writing tools for agents », Code
  Review géré, `/goal`, Opus 5.5 / Sonnet 5.5 / Haiku 5.5 guides. Seulement leur mention via [BP][PB][AT][CR].
- [CR] : `/code-review` tourne dans un sous-agent neuf qui n'a jamais vu la conversation ; effort `low` = peu de faux positifs,
  `medium`→`max` élargit la couverture ; `ultra` = revue cloud multi-agents (coût/limites non lus) ; `--max-findings` 32.
- Je n'ai pas lu la section de [PB] sur « tricher / coder en dur pour les tests » au-delà du titre ; ni le détail des
  « agent team token costs ». Les chiffres [MA] (90,2 %, 15×, 80 %) sont de 06/2025 sur Opus 4/Sonnet 4 : ordres de grandeur,
  probablement dépassés en valeur absolue.
- Les billets [BEA] (12/2024) et [MA] (06/2025) sont anciens ; [HD], [CC], [EVAL] et les guides Fable sont les plus récents.
- Les chiffres de coût de [HD]/[CC] (200 $, 124,70 $, ≈ 20 000 $) sont des expériences d'Anthropic, pas des moyennes.
- Aucune mesure Anthropic d'un « module livré réparé par tours de revue » : notre cas n'a pas d'étalon publié.
