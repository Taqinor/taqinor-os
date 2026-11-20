# Recherche C — qualité logicielle (tests exploratoires, évaluation heuristique, fiabilité, critères de sortie)

Légende des sources : **lu** = page ouverte cette session (WebFetch) ; **lu-recherche** = extrait renvoyé par une recherche web, page non ouverte
(secondaire) ; **mémoire** = de mémoire, à vérifier. Plusieurs sites (satisfice.com, ganssle.com, nngroup.com/www, ppi-int.com) ont refusé la
connexion : les chiffres de Bach/Jones/Nielsen 1993 viennent donc de pages secondaires. 14 recherches web utilisées sur 20.

## 1. L'essentiel en dix lignes
1. Notre boucle « 3 tours de relecteurs neufs + correction entre les tours » est, sans le savoir, du **RITE** (corriger entre deux sessions, vérifier
   la correction au tour suivant — Medlock et al. 2002, lu) et de l'**itération de Nielsen** (« plutôt qu'un gros test, trois séries de 5 : ce qui n'est
   pas corrigé maintenant le sera la prochaine fois », lu 2000/2012). Elle est défendable. Ce qui manque : la MESURE.
2. La formule « 5 relecteurs ≈ 84 % » (1-(1-0,31)^5, Nielsen & Landauer, lu) n'est **pas une garantie** : Faulkner 2003 mesure 55 % à ~100 % selon le
   tirage de 5 (lu-recherche) ; Hertzum & Jacobsen : accord entre deux évaluateurs de 5 % à 65 % (lu-recherche). Un tour « sec » à un seul relecteur est une
   preuve faible.
3. **Estimer le reste** : Lincoln-Petersen N = n·K/k, Chapman N = (n+1)(K+1)/(k+1) − 1 (lu, Wikipédia). Valable seulement sur un périmètre GELÉ, avec deux
   relecteurs indépendants sur la MÊME charte. Notre suite 152 → 78 → ~30 n'est PAS une capture-recapture (les corrections changent la population entre
   les tours, les axes diffèrent) : c'est une courbe de découverte, à lire par relecteur.
4. Alternative moins fragile et bon marché sur une pile jetable : **semer des défauts connus** (5-10) et mesurer la part retrouvée = rappel du relecteur
   (technique de Mills, mémoire ; adaptation = mon inférence).
5. **Charte de session** : « Explorer <cible> avec <ressources> pour découvrir <information> » (Hendrickson, lu-recherche) ; session ininterrompue 1-2 h,
   débriefing court, temps réparti test / enquête-bug / mise en place (Bach 2000, lu Wikipédia).
6. **Critères de sortie** : la définition de « fini » doit exister AVANT et rendre un incrément « utilisable » et « vérifié à fond » (Guide Scrum, lu) ;
   Google (SRE) impose une check-list dont CHAQUE question est justifiée par un incident passé (lu) → modèle exact pour transformer une CLASSE en garde.
7. **Garde permanente** : test d'invariant + liste exhaustive des endroits + preuve que la garde est ROUGE sur le défaut d'origine ; garde taillée à
   l'usage (Google : l'utilité perçue des mutants passe de 20 % à 80 % après boucle de retour, lu-recherche).
8. **Neuf ≠ existant** : pour l'existant on fige d'abord le comportement (test de caractérisation, Feathers, lu), pour le neuf on évite les cas de test
   figés trop tôt (Bach, lu) et on explore. Déploiement progressif à 1-10 % des utilisateurs (Google SRE, lu) pour l'existant en prod.
9. **Rien ne remplace** l'utilisateur et l'appareil réels : l'automatique accessibilité trouve ~57 % des problèmes par volume (Deque 2021, étude de
   fournisseur) ; le « dogfooding » n'est pas un test (Centercode, lu-recherche). Plus petit dispositif : voir §5-Q6.
10. Pièges les plus sérieux : voir §3 (hypothèses de la capture-recapture violées ; indépendance des relecteurs ; bruit des « bug bashes »).

## 2. Pratiques à adopter
| Pratique | Source (statut) | Mécanisme précis | Ce qu'elle aurait changé (§ rétro) | Coût | Niveau |
|---|---|---|---|---|---|
| Courbe de découverte PAR RELECTEUR dans un registre machine | Goel-Okumoto : taux de découverte ∝ défauts restants, m(t)=a(1−e^(−bt)) (lu-recherche) ; rétro §8 | colonne « relecteur-heures » + constats/relecteur par tour ; tracer, extrapoler la queue | §3 : 152→78→30 lus bruts cachaient 6/5/4 relecteurs (25,3 → 15,6 → 7,5 par relecteur) | nul (données déjà là) | L4, L5 |
| 2 relecteurs indépendants sur UNE strate commune par tour, estimation de Chapman | formule lue (Wikipédia) ; hypothèses : population fermée, capture égale ; sous-estimation si violées (Wohlin et al. 1995, lu-recherche) ; revue 2004 : modèle Mh-JK recommandé (lu-recherche) | même charte, même build, comptes séparés ; apparier les constats (id dédoublonné) ; k = communs | §8 « deux relecteurs sur le même périmètre » : donne un reste chiffré au tour 1 | +2 relecteurs par tour (≈ +25 % sur 16 relecteurs) | L5 (L4 : option) |
| Défauts semés (rappel du relecteur) | Mills, 1972 (mémoire) ; adaptation = inférence | 5-10 défauts connus injectés dans la pile jetable (jamais en prod), % retrouvé par relecteur | §6.6 « pas de mesure du niveau » ; §4 « 25 % des correctifs à moitié » | 1 lane haiku + nettoyage | L5 |
| Chartes de session bornées + débriefing | Bach & Bach 2000 (lu Wikipédia) ; Hendrickson (lu-recherche) | charte = cible + ressources + information visée ; 60-120 min ; rapport = charte, notes, bugs, % temps test/bug/setup ; débrief PROOF (passé, résultats, obstacles, reste, ressenti) | §2 étape 2 : nos « rôle + axe » sont déjà des chartes ; manque le % de temps perdu en mise en place (re-semis lents §6.7) | faible | L4, L5 |
| Boucle RITE : corriger entre deux sessions et revérifier | Medlock et al. 2002 (lu Wikipédia, résumé) | « décideurs dans l'équipe de recherche », changement dès qu'un problème et sa solution sont clairs | §2 étapes 4-8 : déjà fait ; l'ajout est la revérification immédiate de la correction par un NEUF (déjà : 25 % à moitié) | nul | L4 |
| « Quality Wednesdays » : polissage continu borné | Linear, Artman, 13/08/2025 (lu) | 1 correction ≤ ~1 h par ingénieur et par semaine, étiquette « quality », thèmes de 1-2 mois (préférences, clavier, accessibilité, mobile) ; > 1 000 corrections en 2 ans | §6.2 coutures, §6.5 cibles jamais atteintes : le petit poli récurrent absorbe le long traîn sans lane | faible, récurrent | L5 (suivi après merge) |
| Check-list de sortie dont chaque ligne cite l'incident d'origine | Google SRE, lancement fiable (lu, date non vue : ancien, livre 2016 de mémoire) | question + action + lien ; revue 1-2 fois l'an pour retirer l'obsolète ; recette graduelle (canari, drapeaux 1-10 %) | §6.1 « même classe 4 fois » : la classe devient une ligne justifiée | moyen au départ | L4, L5 |
| Définition de « fini » écrite au tour 0 | Guide Scrum (lu, version non vue) | élément qui n'y satisfait pas retourne au backlog, ne peut être « livré » | §6.5 cibles chiffrées jamais décidées | faible | L4, L5 |
| Tests de caractérisation avant de toucher l'existant | Feathers (lu) | placeholder → lire la sortie → la figer ; surprise = bug ou documentation | mode EXISTANT : filet avant la vague | moyen | L5 (chemin existant) |
| Triage obligatoire après toute session collective | bug bash : guides (lu-recherche) | un responsable dédoublonne/classe ; sans cela « backlog bruyant » | consolidation §2 étape 3 déjà là | faible | les deux |

## 3. Pièges et contre-indications (dits sans ménagement)
- **Notre lecture des chiffres est biaisée.** 152 → 78 → ~30 mélange : nombre de relecteurs différent (6/5/4), états différents (corrections entre
  les tours = population OUVERTE, contraire à « fermée »), axes différents (capture inégale), et le tour 3 ne compte que « avant le merge ». Extrapoler
  naïvement donne un faux nombre. Calcul indicatif (ma propre arithmétique, hypothèse géométrique) : ratios par tour 0,51 puis 0,38 ⇒ queue
  ≈ 30 × 0,45/0,55 ≈ 25 (ou 19 avec 0,38) ; par relecteur 0,62 puis 0,48 ⇒ ≈ 37. **Fourchette 19-37 « avant le merge » restants après le tour 3** :
  un ordre de grandeur, pas une mesure. Les 2 bloquants + 7 corrections serveur de la vérification finale n'invalident pas ce plafond.
- **Capture-recapture : estimateur biaisé bas si les défauts n'ont pas la même visibilité.** Les défauts « faciles » sont vus par tous, les difficiles
  par personne ⇒ recouvrement trop élevé ⇒ reste sous-estimé (Wohlin et al. 1995, lu-recherche). Avec peu de communs k, l'estimation est instable (seuil
  de k : mémoire, non sourcé). Ne jamais présenter le chiffre sans fourchette ni sans dire « borne basse ».
- **« 5 relecteurs, 85 % »** : Woolrych & Cockton 2001 : la formule suppose une probabilité de découverte constante, ce qui échoue sur des
  tests réalistes (lu-recherche, article non ouvert). Nos relecteurs sont des évaluateurs-experts, pas des utilisateurs : le L=0,31 de Nielsen
  vient d'utilisateurs ; pour l'évaluation heuristique l'« effet évaluateur » domine (accord entre deux évaluateurs : 5-65 % ; médiane 27 % sur
  33 études, lu-recherche). Conséquence pour nous : DEUX tours « secs » avec des relecteurs DIFFÉRENTS, pas un seul tour sec.
- **Contradiction avec la rétro §8 (« acceptation écrite au tour 1 »)** : Bach (lu) met en garde contre les cas de test liants écrits avant d'avoir
  appris le produit ; les formaliser en spec après le constat prouvé (nos gestes de relecteurs) reste sain, les écrire avant non.
- **Dogfooding ≠ test** : « quand le dogfooding remplace le test manuel c'est de la recette interne rebaptisée » (Centercode, lu-recherche) ; les
  « bug bash » complètent la QA, ne la remplacent pas ; noter les participants comme une évaluation individuelle fait chasser les points
  (guide, lu-recherche, source faible).
- **Les tests seuls plafonnent** : Capers Jones, ≈ 85 % de défauts retirés en moyenne (2011), > 95 % exige inspections + analyse statique + tests
  (lu-recherche ; source d'un seul auteur, données propriétaires, ancienne). Pour nous : CI + tests ≈ « test », relecteurs sur écran réel ≈ « inspection » ;
  ne pas déduire de nos 36/36 verts un DRE élevé.
- **Mutation** : coûteuse et bruyante sans boucle de retour (Google, 20 % → 80 % d'utilité perçue après tri, lu-recherche) ; ne pas l'imposer comme porte.
- **Bad-fix injection** (Jones, mémoire) : ≈ 7 % de corrections en introduisent une neuve — cohérent avec nos 3 puis 2 régressions ; à vérifier avant de citer.

## 4. Neuf ou existant
- **Détection** (rétro §8) : module dans `docs/CODEMAP.md` ? routes/écrans/données en prod ? tâches cochées ? verbe de la demande ? — aucune source lue ne
  propose un détecteur ; c'est de la conception maison. Règle ajoutée par cette recherche : si l'écran tourne mais n'a aucun test de caractérisation ni
  baseline de capture, c'est « existant sans filet » → étape de FIGEAGE d'abord.
- **EXISTANT** : (1) figer le comportement (test de caractérisation, Feathers lu ; captures de référence) ; (2) analyse d'impact et sélection des tests
  de régression (mémoire, non lue) ; (3) corriger ; (4) comparer à la baseline ; (5) déploiement progressif (canari, drapeau 1-10 %, retour arrière
  automatique, Google SRE lu). Le Guide Scrum : l'incrément « s'ajoute à tous les précédents et est vérifié à fond » (lu) = la régression fait partie
  du « fini ».
- **NEUF** : pas d'oracle de comportement → exploration par chartes d'abord, cas liants plus tard (Bach lu) ; RITE sur prototype/maquette (Medlock lu) ;
  définition de « fini » + critères d'accessibilité écrits avant la construction.
- Le tour 1 d'un L5 NEUF ressemble à une évaluation de maquette (RITE) ; celui d'un L5 EXISTANT à une session exploratoire sur l'écran réel + figeage.

## 5. Critères de sortie et mesures — réponses aux 6 questions
**Q1 — Combien de relecteurs, et que reste-t-il ?** Sources : Nielsen 3-5 évaluateurs indépendants (lu 2023) ; 5 utilisateurs ≈ 84 % si L=0,31, 3 tours
de 5 (lu 2000). Reco (inférence) : ne pas doubler chaque axe (coût x2) ; faire plutôt **1 relecteur par axe + 2 relecteurs sur une même strate
commune (les 2 écrans centraux)** pour estimer. Formules (lu Wikipédia) : N̂ = n·K/k ; N̂_C = (n+1)(K+1)/(k+1) − 1 ; reste = N̂ − (n+K−k).
Exemple (chiffres INVENTÉS pour illustrer ; la rétro ne donne pas le recouvrement) : A trouve 40, B trouve 35, communs 14 ⇒ LP = 40·35/14 = 100 ;
Chapman = 41·36/15 − 1 = 97,4 ; distincts vus = 61 ; reste ≈ 36-39. Sur les chiffres RÉELS de la rétro (152, 78, ~30) on ne peut calculer que
la tendance par relecteur : 25,3 → 15,6 → 7,5 (§3 : reste 19-37). Si k < ~10, ne pas décider sur l'estimation (seuil : mémoire).
**Q2 — Chartes utiles ?** Aucune source lue ne compare empiriquement des chartes (non trouvé). Forme : cible/ressources/information. Sources de
chartes (Wikipédia, lu) : spécification, plan de test, résultats de sessions précédentes. Inférence : chartes par CLASSE de défaut (frappe perdue :
lent / après un choix / hors ligne / champ non validé ; chiffres contradictoires ; gestes impossibles), car 4 récidives sont venues de là (§6.1).
**Q3 — Critères de sortie défendables (écran)** : (a) 0 constat A ouvert ; (b) B ≤ budget fixé au tour 0 par écran ; (c) rendement du tour
≤ 1/3 du tour 1 par relecteur (rétro : 7,5/25,3 = 0,30 au tour 3 — seuil = ma proposition) ; (d) correctifs revérifiés par un NEUF : ≥ 85-90 %
« réglés », 0 régression (rétro : 85 %, 0 au tour 3) ; (e) reste estimé de A+B (Chapman ou semés) ≤ seuil ; (f) budgets numériques fixes
(position de la 1re ligne, taille de texte, temps de réponse — rétro §6.5) ; (g) accessibilité : 0 violation automatique + liste manuelle
clavier/zoom (l'automatique ≈ 57 % par volume, Deque 2021, fournisseur) ; (h) notes par écran contre une référence nommée, par deux relecteurs
aveugles, accord rapporté — aucune source lue ne donne de seuil de note (SUS : mémoire). Arrêt par règle, pas par tour sec (rétro §3).
**Q4 — Classe → garde** : fiche de classe = invariant en une phrase + liste GREPPÉE de tous les endroits violables + type de garde (test
d'invariant / propriétés / règle de lint / spec e2e) + « née de » (id du constat) + preuve que la garde est ROUGE sur le défaut d'origine + date de
revue (Google SRE : question justifiée par un incident, revue 1-2×/an, lus). Tests par propriétés : générer des entrées (frappe, hors ligne,
collage) ; mémoire, non lu cette session. Tailler les gardes bruyantes (Google mutation, lu-recherche).
**Q5 — Neuf vs évolution** : §4.
**Q6 — Ce que rien ne remplace** : l'utilisateur réel (RITE/Nielsen supposent des participants réels, lu) et l'appareil réel (iPhone/Safari,
notifications, une semaine d'usage — rétro §4 « jamais attrapé »). Plus petit dispositif (inférence) : (1) 1 iPhone réel, 30 min, parcours
écrits, capture d'écran + notes ; (2) Reda ou 1 vrai commercial utilise la version sur 5 jours avec 3 questions de débriefing (PROOF allégé) ;
(3) activation par drapeau sur 1-10 % (Google, lu) ; (4) journal minimal d'erreurs front. Le dogfooding sert la connaissance du produit, pas la
détection (Centercode, lu-recherche).

## 6. Non couvert, non trouvé, douteux
- Non lu en entier (refus réseau) : Bach & Bach 2000 (satisfice), Nielsen & Landauer 1993, Capers Jones, Linear « zero-bug », Hertzum, Woolrych &
  Cockton, Faulkner (abstract seulement) : chiffres repris via pages secondaires.
- Non trouvé : comparaison empirique de types de chartes ; seuils de notes de qualité d'écran contre une référence ; exemples publics de QA de
  design chez Linear/Apple HIG (seul Quality Wednesdays lu) ; régression visuelle (non cherchée, budget) ; parcours cognitif ; tests de mutation
  UI ; données DRE indépendantes de Jones.
- Mémoire non vérifiée : Mills (semis), Jones (bad-fix 7 %), propriétés/QuickCheck, SUS 68, sélection de tests de régression, seuil de k.
- Douteux : vendeur Deque (57 %) ; seuil « <50 % sur charte » (non confirmé, écarté) ; le livre SRE (2016) peut être dépassé.
