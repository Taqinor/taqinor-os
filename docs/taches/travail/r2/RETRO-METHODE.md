# Rétrospective de méthode — les tours de revue du module Tâches (19-20/11/2026)

But de ce fichier : garder TOUT ce qu'on a fait et appris, pour en tirer deux niveaux de travail neufs (« L4 » et « L5 »)
au-dessus de L1-L3 (`.claude/skills/go-deep/SKILL.md`). Écrit par l'orchestrateur à la fin du chantier, à partir de ce
qu'il a observé ; les chiffres viennent des rapports cités (dossier `docs/taches/travail/r2/`).

## 1. La demande et le point de départ
- Reda, module « Tâches » livré (179 tâches cochées, 4 fusions, CI verte, acceptations en direct « 44 / 44 », en prod) :
  « look at what was done, and redo multiple rounds on functionalities, simplicity and beauty ». Règle : aucune question.
- Constat fondateur de toute la méthode : **un module « fini » selon le plan, la CI et les acceptations a rendu 152 constats
  au premier tour sur l'écran réel**, dont des pertes de frappe, des chiffres contradictoires, des gestes impossibles.

## 2. Ce qu'on a fait, dans l'ordre (la boucle qui a marché)
0. **Lire l'existant** : un agent d'inventaire écrit `etat-des-lieux.md` (ce qui existe, ce qui a été laissé, ce qui a
   été décidé seul, ce qui n'a jamais été vérifié, promesse par promesse de la demande d'origine).
1. **Une pile PRIVÉE et jetable** (`pile-locale.md`) : base clonée d'un gabarit, conteneur Django à part, Redis à part,
   front construit et servi, comptes de revue semés (un par relecteur + un compte vide + un par lane), un outil de
   capture de tous les écrans en 4 vues (iPhone / bureau × clair / sombre). Ne jamais toucher la pile d'une autre session.
2. **Un tour de revue** = des relecteurs NEUFS (opus, effort high), chacun un RÔLE et un AXE (fonctions boucle
   quotidienne ; fonctions planification ; simplicité premier jour ; simplicité usage quotidien ; beauté iPhone ; beauté
   bureau), un compte à lui, un brief commun (`brief-revue.md`) : utiliser le produit comme le fondateur, PROUVER chaque
   constat (gestes + capture + attendu), gravité A/B/C, comparer aux meilleurs produits, dire aussi ce qui est bien et
   ce qui n'a pas été essayé, écrire au fil de l'eau.
3. **Consolidation** (un agent opus) : dédoublonner, VÉRIFIER chaque constat contre le code (cause `fichier:ligne`),
   écarter les artefacts de la pile et le hors-périmètre, trancher les choix de produit sans question (option la plus
   simple, sinon la maquette ; ce que font les meilleurs), ranger en lanes STRICTEMENT disjointes en fichiers avec la
   table fichier → lane, dire l'ordre de pli imposé et le modèle par lane.
4. **Correction** par lanes en worktrees isolés (`brief-lane.md`) : test rouge d'abord, correction à la racine, jumeaux,
   preuve sur l'écran réel (son build, son port, son compte, capture « après » regardée), un commit par correction,
   rapport avec ce qui n'est PAS vérifié et ce qu'il faut demander aux autres lanes.
5. **Pli** par l'orchestrateur (`git merge --no-ff` dans un worktree d'intégration), tenue d'un fichier de RESTES
   (`vague2.md`, `vague3-restes.md`…) où atterrissent les demandes croisées et les interfaces exposées ; messages aux
   lanes encore en vol quand une dépendance est pliée.
6. **Couture** : une lane SEULE sur l'arbre règle les coutures entre lanes, rejoue les specs e2e contre le build
   assemblé et fait une passe d'assemblage sur tous les écrans.
7. **CI d'abord** : PR brouillon ouverte tôt, Auto-fix allumé ; chaque rouge lu par un éclaireur haiku (journal du job),
   renvoyé à la lane qui possède le fichier ; jamais de contrôle désactivé ni d'exemption.
8. **Tour suivant par des relecteurs NEUFS** qui (a) contre-vérifient chaque correction (réglé / à moitié / pas réglé /
   régression), (b) portent un regard neuf. On recommence 3 → 7 jusqu'à ce que le tour soit presque sec.
9. **Dernier tour** : chaque constat marqué « avant le merge » ou « peut attendre » ; seule la première liste est
   corrigée ; puis UNE vérification ciblée (un relecteur neuf) et UNE critique adverse du diff serveur (sécurité,
   isolation entre comptes, perte de données) ; merge par la file ; mémoire et README.

## 3. Les chiffres
| Tour | Relecteurs | Constats | Corrections | Contre-vérification au tour suivant |
|---|---|---|---|---|
| 1 | 6 | 152 | 102 (`R2`), 8 lanes + 3 + couture | 143 réglées, 37 à moitié, 5 pas réglées, 3 régressions (sur 191) |
| 2 | 5 | 78 neufs | 84 (`R3`), 7 lanes | ≈ 85 % réglées, 2 régressions |
| 3 | 4 | « avant le merge » seulement | 27 (`R4`), 3 lanes + 2 coutures | 23 réglées, 3 à moitié, 0 régression |
| final | 1 + 1 critique serveur | 2 bloquants + 7 corrections serveur | faites | — |
- ≈ 40 agents de correction, 16 relecteurs, 3 consolidations ; 246 fichiers, +22 958 / −4 029 lignes ; tests front du
  module 1 074 → 1 269 ; CI 36 / 36.
- Coût : ≈ 74 points du quota hebdomadaire Ultra (6 % → 80 %), dont une part pour une autre session en parallèle ;
  le contexte de l'orchestrateur a fini à 90 % (une compaction au milieu).
- La courbe : 152 → 78 → ~30 « avant le merge » → 2 bloquants. Elle ne tombe PAS à zéro : on arrête sur une règle
  (« avant le merge » seulement), pas sur un tour sec.

## 4. Ce que chaque étage a attrapé que les autres n'attrapaient pas
- Plan + tests unitaires + acceptations : la présence des fonctions. Pas l'usage.
- Relecteurs sur l'écran réel : pertes de frappe, gestes impossibles, chiffres qui se contredisent, laideur, mots obscurs.
- Contre-vérification par des NEUFS : ≈ 25 % des corrections « faites et prouvées » par leur auteur n'étaient réglées
  qu'à moitié ; 3 puis 2 régressions.
- CI : ≈ 50 défauts de schéma latents (le compte de fuzz n'avait pas le droit de voir le module : un contrôle qui ne
  lisait rien), un geste non cliquable né de l'assemblage de deux lanes (clic intercepté), une lettre avalée sous
  charge (test « instable » = vrai défaut), l'accessibilité (axe 4.14 contre 4.12 du poste), les gardes de la maison.
- Critique adverse du diff : une régression de collage (point vide → tout refusé), une tâche comptée sur deux jours.
- Vérification ciblée finale : une action tapée perdue à « Terminer », une première ligne de README fausse.
- JAMAIS attrapé (hors de portée) : le vrai iPhone / Safari, les notifications, un vrai usage d'une semaine.

## 5. Ce qui a marché (à garder tel quel)
1. Juger sur l'écran RÉEL, avec preuve (gestes + capture), jamais sur le code ni sur un build vert.
2. Des relecteurs neufs à chaque tour ; l'auteur d'une correction ne la valide jamais.
3. Rôles et axes distincts (fonction / simplicité / beauté ; iPhone / bureau) + comparaison nommée aux meilleurs.
4. La consolidation qui vérifie contre le code et rend des lanes disjointes en fichiers, avec la table.
5. Le fichier de restes tenu au fil des plis ; les interfaces entre lanes écrites noir sur blanc (prop, événement,
   contrat d'API d'abord).
6. Une lane de couture seule sur l'arbre après chaque vague ; rejouer les specs e2e contre le build assemblé.
7. Les sujets récurrents traités comme une CONCEPTION d'ensemble (« un chiffre, une source », « le matin encombré »,
   « une frappe ne se perd jamais »), pas symptôme par symptôme.
8. Les choix de produit tranchés par règle écrite (le plus simple pour l'utilisateur, sinon la maquette, ce que font
   les meilleurs), notés, réversibles, redits au README.
9. Un éclaireur haiku pour lire les journaux de CI ; l'orchestrateur ne lit que des résumés.
10. Écrire l'état sur disque et sur GitHub à chaque étape (`ETAT.md`) : la session a survécu à une compaction et
    pouvait être reprise d'un autre poste.

## 6. Ce qui a coûté cher ou mal tourné (à corriger dans la méthode)
1. **La même classe de défaut est revenue quatre fois** (frappe perdue : en ligne lent, après un choix, hors ligne,
   champ non validé) : chaque lane corrigeait un symptôme. Il faut, dès la consolidation, nommer la CLASSE, écrire
   l'invariant, et exiger la liste de tous les endroits où il peut être violé.
2. **Les coutures entre lanes** ont produit des défauts neufs à chaque vague (nom de classe CSS différent des deux
   côtés, bouton + caché sur la journée vide, titre qui recouvre des boutons, tests qui attendent l'ancien code HTTP).
   Les lanes disjointes en fichiers ne sont pas disjointes en COMPORTEMENT.
3. **Un changement transversal lancé tard** (refus d'état 400 → 409 pour satisfaire api-fuzz) a touché tous les écrans
   et tous les tests pendant qu'une vague tournait : 5 allers-retours de CI. Un changement de contrat global se fait
   SEUL, avant la vague, avec la table de ce qui change.
4. **Le poste n'est pas la CI** : dépendances du poste en retard sur le lock, horloge réelle, compte de démonstration
   différent, base de fuseaux périmée ; chaque écart a coûté un aller-retour.
5. **Les mesures « cibles » jamais atteintes traînent** (première tâche ≤ 260 pt, Tableau ≤ 260) faute d'un critère de
   sortie chiffré décidé au début.
6. **Pas de mesure objective du niveau** avant le tour 3 (notes sur 10 par écran contre une référence nommée) : on ne
   savait pas dire « c'est mieux » autrement que par le nombre de constats.
7. **Le coût** : 16 relecteurs opus à ≈ 400 k tokens, 40 lanes à ≈ 500-800 k. Une partie évitable : captures relues
   plusieurs fois, re-semis lents, lanes qui reconstruisent le front, orchestrateur Fable qui porte tout le contexte.
8. **L'orchestrateur est le goulot** : il plie, relaie, trie la CI ; son contexte se remplit de rapports. Il faudrait
   des rapports plus courts, un registre machine des constats (id, état, preuve) plutôt que de la prose, et un agent
   « plieur ».
9. **Rien sur un vrai appareil ni sur une vraie semaine d'usage** : le dernier étage de vérité manque.
10. Pannes d'outillage : lancer plusieurs agents isolés dans un même message (échecs de worktree) ; `git worktree
    remove` qui suit une jonction `node_modules` ; Postgres partagé saturé ; un fichier temporaire hors arbre impossible
    à supprimer.

## 7. Ce que la méthode suppose (conditions d'emploi)
- Le module EXISTE et tourne (c'était une AMÉLIORATION, pas une construction) : on part de l'usage, pas d'une page
  blanche. Pour une construction neuve, les étapes d'avant (comprendre la demande, références, conception, maquettes,
  contrat, plan, fusions) sont celles des 17-18/11 (`docs/taches/conception/`, `PLAN_TACHES.md`, `PASSATION.md`).
- Un écran pilotable (Playwright), des comptes de démonstration semables, une pile qu'on peut monter à part.
- Une CI rapide (≈ 10-15 min) et une file de merge.
- Un périmètre de fichiers possédé (le module) pour que les lanes ne débordent pas.

## 8. Idées pour un niveau au-dessus (à confronter à la recherche)
- Un REGISTRE des constats (fichier de données : id, axe, gravité, classe, preuve, état par tour) qui remplace les
  rapports en prose ; la courbe de découverte par tour et une estimation de ce qui reste (deux relecteurs indépendants
  sur le même périmètre → recouvrement).
- Des CRITÈRES DE SORTIE chiffrés décidés au tour 0 (notes par écran contre une référence, zéro A, budget de gestes,
  position de la première ligne, tailles de texte, temps de réponse).
- Les classes de défauts transformées en GARDES permanentes (tests d'invariant, règles de lint, specs) pour ne pas
  revenir.
- Des parcours rejoués à chaque vague par une suite d'acceptation écrite au tour 1 (les gestes des relecteurs
  deviennent des specs).
- Un étage « vraie vie » : appareil réel, données réelles anonymisées, une semaine d'usage instrumentée, retour du
  fondateur en trois minutes plutôt qu'aucune question.
- Détection automatique NEUF / EXISTANT : le module est-il dans `docs/CODEMAP.md` ? a-t-il des routes, des écrans, des
  données en prod, des tâches cochées ? la demande dit-elle « build » ou « improve / review / redo » ? → deux chemins.
