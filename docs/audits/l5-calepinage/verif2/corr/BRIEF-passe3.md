# Brief — passe finale de cohérence de TOUTE la vague 2 (campagne L5 calepinage, 21/11/2026)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## La situation
Environ 470 tâches de plan (module Calepinage de TAQINOR OS, ERP solaire Django + React) ont été vérifiées contre le
code puis corrigées en deux passes, lot par lot (18 fichiers `src-*.md`). Chaque lot passe son validateur. Il reste ce
qu'aucun correcteur de lot ne pouvait régler : les incohérences ENTRE lots, et quelques points de fond. Tu es le SEUL
écrivain maintenant : tu peux éditer tous les `src-*.md`. Tu édites du TEXTE de tâches — tu ne construis rien, tu ne
touches à aucun fichier d'un dépôt.

## À lire d'abord
1. `…\scratchpad\l5\corr\BRIEF-correcteur.md` (format des blocs, outils, règles qui ne bougent pas) et
   `…\scratchpad\l5\corr\BRIEF-passe2.md` (arbitrages et règles R1 à R7 : ils restent vrais).
2. Tous les `…\scratchpad\l5\corr\croises-*.md` (demandes entre lots ; beaucoup sont déjà appliquées — vérifie dans
   le texte avant d'agir).
3. La sortie du contrôle de cohérence, à relancer toi-même autant que nécessaire :
   `PYTHONIOENCODING=utf-8 python "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/coherence_vague.py" "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/l5/corr" "C:/dev/taqinor-os/.claude/worktrees/l5-vague2-integ"`
4. La critique finale `…\scratchpad\l5\verif2\CRITIQUE-fable-vague2.md` (§ 2, § 5, § 6, § 7) pour le contexte des points ci-dessous.
Dossier : `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\`.
Code de référence (`main` d'aujourd'hui), lecture seule (Grep, Glob, Read ; `check_ownership.py --owner-of` permis ;
ni docker, ni tests, ni serveur) : `C:\dev\taqinor-os\.claude\worktrees\l5-vague2-integ\`.

## A. Ce que le contrôle de cohérence doit rendre à la fin
- « CYCLES : 0 ». Connus : 548 ↔ 714 — ordre retenu : **714 d'abord** (le réglage société, valeur de départ), **548
  ensuite** `(@after: ACAL714)` (la valeur du dossier prime et l'écran le dit ; ce qui, dans 714, parle de la valeur
  du dossier ou d'un paramètre `origine` passe dans 548). 778 → 778 : une tâche ne dépend pas d'elle-même.
- « @after vers une tâche SUPPRIMÉE : 0 », « vers un id INCONNU : 0 », « texte qui cite une tâche supprimée : 0 »
  (hors la phrase `SUPPRIMÉE : …` des blocs supprimés eux-mêmes).
- « @after vers une tâche BLOCKED/GATED du plan » : ces tâches-là (470, 436, 434, 441, 428, 442, 423, 432…) ont leur
  CODE livré sur main ; seule leur preuve en direct attend. Retire le tag `@after` et écris « s'appuie sur ACALnnn
  (code livré sur main) » — sauf ACAL1026 → ACAL487, qui reste (487 est une vraie tâche à construire, que
  l'orchestrateur dé-gatera).
- « déclare apps/calepinage/selectors.py » : exactement les neuf de la vague 0 (572, 595, 770, 883, 895, 948, 961,
  964, 978). Aucune de ces neuf ne porte d'`@after` vers une tâche qui déclare un fichier `frontend/src/` ou
  `apps/web/src/` du calepinage sans déclarer elle-même un fichier serveur (sinon la construction se bloque) :
  vérifie-le et corrige l'ordre s'il le faut.
- « déclare apps/calepinage/urls.py : 0 », « reste de gabarit %s : 0 » (686), « tampon gen manuel absent : 0 ».

## B. Points de fond à régler (recontrôle chaque fait dans le code avant d'écrire)
1. **647 et 725** (marquage des modules à optimiseur) : aujourd'hui chacune dit créer la fonction partagée
   (`equiperModules` dans 647, `marquerModules` dans 725). Ordre retenu : **725 d'abord** (elle expose
   `marquerModules(modules, valeur)`), **647 ensuite** `(@after: ACAL733, ACAL631, ACAL725)` qui l'APPELLE et ne crée
   aucune fonction jumelle.
2. **867 et 1193** (étape Documents) : la maquette `docs/audits/l5-calepinage/maquettes/Documents.dc.html` fait foi —
   « Dossiers » et « Approbation » passent au niveau expert (1193). Retire de 867 toute phrase qui les garde visibles
   au niveau essentiel.
3. **1033** (format « une page » du devis : plus d'« économies estimées » imprimées sans consommation connue,
   D-ACAL-40) : c'est un changement visible du client. Il ne doit toucher QUE les nouveaux rendus : conditionne-le par
   `regles_au_moins(devis, 15)` (niveau posé par ACAL998), `(@after: ACAL998)`, clause « Chiffre client : nouveaux
   rendus seulement ; devis déjà envoyés inchangés ; écarts montrés à Reda avant activation » ; ajoute ACAL1033 à la
   liste `@after` et à la condition GATED d'ACAL1001. Vérifie de même ACAL976 et ACAL927.
4. **921 et les documents déjà enregistrés.** 921 change ensemble l'écrivain du balayage automatique
   (`calepinage/services/balayage.py`, qui écrit « face − 90 ») et le lecteur (qui ajoute + 90). Les documents DÉJÀ
   enregistrés par l'ancien balayage seraient alors relus décalés de 90°. Lis le code (écrivains : atelier et balayage ;
   lecteurs) et établis ce qui est vrai aujourd'hui pour chaque écrivain. Puis écris la solution honnête : après 921,
   AUCUN document déjà enregistré ne doit être relu autrement qu'avant sans que ce soit voulu et montré. Voies
   possibles : une clé de convention écrite dans le document (contrat d'abord) que le lecteur respecte ; ou la
   correction du seul écrivain fautif ; plus, si des documents existants sont réellement faux aujourd'hui, une tâche
   de LISTE en lecture seule (commande `--dry-run` qui nomme les calepinages concernés) et une tâche d'application
   GATED « attend que Reda ait lu la liste » (règle permanente : aucune réparation de données sans liste montrée
   d'abord). Dis dans ton compte rendu ce que le code t'a montré.
5. **D-ACAL-36 et les marchés.** La décision du fondateur dit : « les NOUVEAUX devis qui ont un calepinage enregistré
   impriment la production de la pose réelle » — sans restriction de marché. ACAL999 rend `None` pour un marché non
   résidentiel. Vérifie dans le code d'où vient la production imprimée d'un devis commercial / industriel
   (`moteur_ci/production.py::bloc_production_ci`, `etude.py::run_bankable_study`, `_zone_base_production`) et d'un
   devis agricole : si elle suit déjà l'orientation réelle des pans du calepinage, écris-le dans le Constat de 999
   avec la preuve ; si elle vient du standard de la ville, il manque la moitié C&I : écris la ou les tâches (plans
   des propriétaires, niveau 15, mêmes garanties pour les devis envoyés, `@after` vers 1001 mis à jour). Le pompage
   agricole (dimensionné sur la pompe) : dis ce qu'il en est, sans rien inventer.
6. **Vue 3D publique d'un calepinage « rapide ».** Choix déjà pris : un dessin automatique non vérifié n'est jamais
   montré au client. Le lot D8 signale que la vue 3D de la page publique du devis (`_safe_roof_layout`, côté ventes)
   n'est pas couverte par ACAL1008. Vérifie le chemin dans le code ; s'il existe, écris la tâche qui le ferme (plan
   du propriétaire du fichier, `@after: ACAL1006`, ajoutée aux `@after` d'ACAL1001).
7. **Demandes croisées restantes** : applique celles qui ne le sont pas encore — notamment `croises-D4-a` (548),
   `croises-D5-b` (547, 838, 887 / 888), `croises-D7-a` (572 pour 939 ; 606, 609, 602, 603, 770, 613, 612),
   `croises-D7-c` (600, 878, 884 : `@after: ACAL978` seulement si ce sont des écrans qui éditent le même fichier ET
   que cela ne crée pas de cycle), `croises-D1-a` (extraction `layoutResnap.ts` de 510 face à 574 : un seul des deux
   crée le module), `croises-AUTRES-PLANS` (846 importe `apps.sav.selectors_releves`), `croises-D6-b`, `croises-D8`.
   Une demande que tu juges fausse : ne l'applique pas, dis pourquoi.
8. **ACAL1031 (acceptation)** : régénère la liste des ids couverts depuis les tâches VIVANTES de la vague (toutes sauf
   les GATED et elle-même), en plages compactes ; elle reste une consigne pour l'orchestrateur.
9. **Rangement des tâches neuves.** Écris `…\scratchpad\l5\corr\rangement-nouvelles.md` : une ligne par id créé
   pendant les corrections (tout id ≥ ACAL1033), au format `ACALnnnn | <M1|M2|GATED> | <D1…D8> | <id de la tâche
   juste après laquelle la ranger>` — M1 pour ce qui corrige un chiffre faux vu du client ou une chose calculée sans
   écran, M2 sinon.

## Contrôle avant de rendre
Pour CHAQUE lot dont tu as modifié le fichier : les deux commandes du brief de première passe (`rejoint`, puis
`valide_lot2.py`) — aucune « ALERTE », « 0 en echec » (exception admise : lignes « proprietaire de … » des tâches
rangées dans un autre plan que calepinage, vérifiées par `check_ownership.py --owner-of`). Puis le contrôle de
cohérence, qui doit rendre ce que dit la partie A. Sur toute tâche modifiée : mention
`STATIQUE (lecture du 21/11 sur 684d77f02)` et tampon `(gen manuel 684d77f)`.

## Compte rendu (45 lignes au plus)
Partie A : chaque compteur avant → après. Partie B : point par point, ce que le code a montré et ce que tu as écrit
(ids). Tâches créées (id, plan, une ligne) et supprimées. Demandes croisées refusées et pourquoi. Sortie finale du
contrôle de cohérence (les titres `## …` avec leurs comptes, et la ligne « par plan »). Ce que tu n'as pas vérifié.
