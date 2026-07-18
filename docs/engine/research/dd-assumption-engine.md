# L'Assumption Engine — le plan marketing comme arbre vivant de croyances testées

**17 juillet 2026 · dossier de conception + verdict · destiné à `docs/engine/research/` après l'atterrissage du run nocturne.**
Sources : 5 dossiers de recherche de ce round (`at-practice`, `at-science`, `at-decay`, `at-precedents`, `at-benchmarks`, session scratchpad) + les dossiers committés `docs/engine/research/dd-*.md`. Idée d'origine : Reda, 16/07/2026 au soir.

---

## 1. Le verdict, sans politesse

**L'idée est une synthèse solide de trois composants séparément prouvés, plus UN mécanisme sans précédent marketing CONNU (cherché dur, pas trouvé — l'analogue le plus proche vit dans l'ordonnancement de tests de régression logicielle) — et l'ensemble se réduit à ~50 lignes de mathématiques qui rendent le plan de vol ADSENG auto-ordonnancé.** Ce n'est pas une invention à partir de rien : c'est un assemblage que personne ne vend. Pour un homme de brevets : les assemblages se construisent, et celui-ci est constructible sur ce qui est déjà dans le plan. **Et la déflation la plus dure de la recherche, servie entière : à ~15 décisions de test par an, un humain avec un tableur fait ça très bien — le gain de l'automatiser est la DISCIPLINE (aucune décision oubliée, aucun biais de récence, un journal complet) et l'histoire produit multi-tenant, pas l'optimalité statistique.** C'est un gain réel, mais c'est celui-là.

**Ce qui existe déjà, sous quel nom (vérifié) :**

| Ton idée | Le nom établi | État de l'art |
|---|---|---|
| « Un plan = des résultats d'A/B supposés » | Assumption mapping (David Bland, ~2013 : importance × évidence) ; Opportunity Solution Tree (Teresa Torres) ; Goal Tree (Speero) | Ateliers MANUELS sur post-its — jamais un logiciel vivant |
| « Tester le plus incertain d'abord » | Value of Information / Knowledge Gradient (Frazier–Powell 2008) ; en version artisanale : scores ICE/PIE des équipes growth | Formalisé depuis des décennies ; les outils (Optimizely/Eppo/GrowthBook) scorent Potential/Importance/Ease — jamais la récence |
| « Retester même les acquis » | Champion/challenger perpétuel (credit-risk FICO, années 1980) ; non-stationnarité = discounted Thompson sampling (Raj–Kalyani 2017), discount DLM (West–Harrison) | Perpétuel chez FICO à des volumes 1000× les nôtres ; les cadences de retest pub publiées = folklore vendeur (ni Meta ni Google ne publient de règle) |
| « Emprunter aux autres domaines sans données » | Hierarchical/empirical Bayes (partial pooling) ; Hong et al. AISTATS 2022 (hierarchical Bayesian bandits) ; **Amazon KDD 2024** (multi-task bandits budget, −12,7% CPC en prod) ; Google MMM hiérarchique (Jin 2017) ; GrowthBook James-Stein (intra-compte) | Statistique standard ; le précédent prod Amazon est EXACTEMENT ce pattern — même annonceur, multi-campagnes |
| « Ré-ordonner par date du dernier test » | **AUCUN précédent marketing trouvé** (cherché dur). L'analogue le plus proche vient de l'ordonnancement de tests de régression EN GÉNIE LOGICIEL | **Le morceau réellement neuf.** À construire, pas à supposer validé ailleurs |

**Meta possède la plateforme d'expérimentation adaptative la plus aboutie du monde (Ax/BoTorch, open-source) et aucune trace publique ne montre son application aux campagnes publicitaires — pas même en interne** (Ax tune des hyperparamètres ML, du hardware AR/VR, du béton — pas des ads). Albert.ai, le « premier marketeur autonome » (2010), a fini revendu discrètement en 2022, exigeait des créas humaines, et un évaluateur tiers le jugeait inadapté aux petits volumes. Personne n'a fusionné ces morceaux, et surtout pas pour un compte SMB.

**Les trois corrections obligatoires à ton énoncé :**

1. **« Le plus incertain d'abord » est faux tel quel.** L'incertitude n'est qu'un des multiplicandes. Sans le terme de testabilité, ton moteur pointera son unique slot de test vers les barreaux lead-qualifié/signature — les plus incertains du funnel ET les seuls qu'il ne pourra jamais résoudre (notre propre math MDE : 79–158% d'effet minimal détectable au barreau qualifié, >300% à la signature). Le bon critère : **VoI par dirham = enjeux × pertinence-décision × testabilité / coût**, avec la testabilité qui ÉCRASE le score quand le MDE est infaisable.
2. **Le retest perpétuel a un prix qu'on ne peut pas se payer en calendrier fixe.** À ~12–17 slots de test/an (3-4 semaines/test à 100 MAD/j), chaque revalidation coûte une nouvelle branche, une pour une. La solution n'est PAS un planificateur de retests : c'est de laisser la péremption gonfler l'incertitude du nœud (voir §3) jusqu'à ce que son VoI redevienne compétitif. Le retest s'auto-programme quand il le mérite — jamais parce qu'un calendrier le dit.
3. **À budget actuel, l'arbre restera petit.** 2 à 4 nœuds vivants (hook/format/angle/audience), le reste = croyances non testées qui vivent sur leurs priors. C'est un peu nu par rapport à la métaphore — et c'est très bien : la discipline vaut plus que la taille. L'arbre grandit avec le budget, et il explose en valeur dans le PRODUIT (un arbre par tenant + priors partagés intra-tenant légaux).

**Ce que je garderais mot pour mot de ton énoncé : « l'arbre EST l'historique du plan ».** C'est la pièce la plus profonde. Le document de plan devient une projection de l'état de l'arbre à l'instant t. C'est exactement l'extension naturelle du FlightPlan ADSENG (aujourd'hui une séquence linéaire de phases) vers une file de priorités auto-ordonnancée.

---

## 2. Ce que dit la donnée sur la décroissance des « vérités » (pourquoi ton instinct de retest est fondé)

| Classe d'hypothèse | Vitesse de péremption | Évidence |
|---|---|---|
| Créatif (une exécution précise) | **Jours → 2 semaines** à notre volume | Meta (équipe Analytics, 2023, mesure directe) : réponse ∝ (N+1)^−0,43 par exposition répétée ; −45% dès la 4e exposition ; exposition moyenne écosystème déjà 4,2 |
| Angle/message (« facture d'été ») | **~2 trimestres** (indicatif) | Expérience naturelle Nielsen : les pubs à thème COVID passent de 48% → 20% de part en 2 trimestres — un choc macro, pas une décroissance d'angle en régime stationnaire ; la vitesse stationnaire reste un trou d'évidence [NON VÉRIFIÉ] |
| Audience/structure | Trimestres (précis non établi) | Consensus praticiens (saturation lookalike) ; AUCUNE étude académique propre — [NON VÉRIFIÉ] |
| Économie de la catégorie (tranches ONEE, FDA…) | Quasi-jamais (événements réglementaires) | Par nature ; surveillée par la watchtower 7.2, pas par l'arbre |
| Cadence officielle de retest | **N'existe pas** | Ni Meta ni Google ne publient de règle ; « annuel/trimestriel » = folklore vendeur |

Conclusion : des demi-vies PAR CLASSE, pas une cadence globale. C'est précisément ce que la mécanique du §3 encode.

---

## 3. La mécanique unifiée — une boucle, ~50 lignes

**L'insight central de la recherche : tes trois « fonctionnalités » sont UNE seule boucle.** Un posterior actualisé avec oubli + une règle d'acquisition VoI = l'arbre vivant entier. Le ré-ordonnancement par péremption n'est même pas du code : il tombe gratuitement du gonflement de variance.

### 3.1 L'état d'un nœud
Chaque `AssumptionNode` j porte un posterior Beta(α_j, β_j) sur son taux (ex. taux de conversation par impression du hook « facture », relatif au champion).

### 3.2 L'oubli (la péremption devient mathématique)
Chaque semaine SANS test du nœud : (α, β) ← (ρ·α + (1−ρ)·α₀, ρ·β + (1−ρ)·β₀), avec ρ = 0,5^(1/H) et H la demi-vie de la CLASSE : **H = 8 sem (créatif), 13 sem (angle), 26 sem (audience/structure)**. C'est le pas d'évolution d'un modèle état-espace (forme discount de West–Harrison, δ~0,97–0,99 — technique de manuel, pas une astuce). La variance regonfle vers le prior ; un « acquis » de janvier redevient incertain en avril À LA VITESSE DE SA CLASSE. Deux horloges distinctes : le bandit intra-test oublie par impression ; l'arbre oublie par semaine.
**La saisonnalité CONNUE (Ramadan, été) n'est PAS de l'oubli : c'est un tag de contexte** — un nœud saisonnier a des posteriors séparés par saison, réactivés quand la saison revient.

### 3.3 Le score (la file de priorités)
Quand un slot de test s'ouvre (cadence de rotation hebdo) :
**VoI_j = S_j × U_j × R_j × T_j / C_j** — enjeux S (part du budget que la réponse pilote, pondérée revenu), **incertitude U_j = 1 − |2·P(meilleur)_j − 1|, recalculée CHAQUE SEMAINE depuis le posterior oublié** (c'est LE terme qui regonfle quand un nœud vieillit — sans lui, la file ne re-fait jamais surface aux nœuds périmés et tout le §3.2 devient décoratif), pertinence-décision R (une réponse changerait-elle une action ? un nœud « intéressant mais sans conséquence » score 0), **testabilité T_j = clip(δ_plausible/δ_MDE, 0, 1)** (δ_MDE calculé par le service ADSENG13 aux volumes courants — le clip qui empêche de viser l'intestable), coût C (semaines × part de budget). Le moteur teste argmax VoI. Un vieux gagnant regonflé re-gagne la file par U — le retest s'auto-déclenche, jamais par calendrier.

### 3.4 Démarrage à froid (ton idée « autres domaines »)
Prior d'un nœud neuf = ajustement méthode-des-moments d'une Beta sur les agrégats des nœuds frères/de la catégorie (même tenant), **plafonné à κ_max = min(50, ~1 semaine d'événements)** : la donnée locale domine en ~1 semaine. Pattern nommé et éprouvé (AISTATS 2022 ; Amazon KDD 2024 en prod). **Intra-tenant uniquement pour l'instant** — voir §6 pour le cross-tenant.

### 3.5 Interactions (l'honnêteté sur l'arbre)
Un arbre one-variable-at-a-time rate les interactions (un hook qui ne gagne qu'en vidéo). Aux ~15 tests/an, un plan factoriel ne ferait que diluer un volume déjà maigre (plancher de détection ±18–35% même au sommet du funnel) — **OFAT autour du champion est défendable par nécessité, pas par optimalité**. Le modèle de données garde quand même des liens d'invalidation (parent bascule ⇒ enfants marqués périmés en cascade) : un DAG léger, pas un arbre pur.

---

## 4. Le contrat des points de contact IA (ta question « l'IA seulement au début »)

**Confirmé faisable.** Après l'amorçage, le moteur tourne indéfiniment sans IA. Le résidu irréductible est court et nommable :

| Fréquence | Qui | Quoi |
|---|---|---|
| Amorçage (jour 0) | Claude + toi | Semer l'arbre : nœuds (énoncé FR, classe, enjeux, pertinence, tags saison, liens d'invalidation, priors en pseudo-comptes) + le backlog créatif 3-6 mois + les gabarits. UN format de fichier de semis (YAML) = tout le contrat |
| Trimestriel (ou mensuel si tu veux) | Claude + toi (1 session) | (1) Nouvelles branches (idées neuves — l'arbre ne peut que recombiner ce qu'il contient) ; (2) arbitrage des nœuds « intestables » que l'arbre voudrait tester (T≈0 : jugement humain sur les barreaux argent) ; (3) recharge du backlog créatif ; (4) lecture des propositions de divergence proxy-vs-CRM |
| Jamais | — | Choix du test, allocation, promotion, retrait, re-test, pacing, garde-fous : 100% déterministe (doctrine ADSENG inchangée) |
| Rare | Toi seul | Unpause, plafonds, kill-switch |

**La borne honnête : la qualité des mois autonomes = la richesse du semis.** Le moteur exécute une stratégie ; il n'en invente pas. Un semis pauvre tourne en rond proprement.

---

## 5. Intégration ADSENG — c'est une EXTENSION, pas une refonte

Tout s'appuie sur des modèles déjà planifiés : Experiment/Arm (ADSENG3), le bandit (ADSENG8), l'échelle des récompenses (ADSENG9), le service MDE (ADSENG13 — fournit δ_MDE au clip de testabilité), DecisionLog (ADSENG12), FlightPlan/Phase (ADSENG5), la rotation (ADSENG25), la simulation (ADSENG36). L'Assumption Engine remplace UNE chose : la transition de phase FIXE du FlightRunner (ADSENG35) devient « la prochaine phase = argmax VoI ». Compatibilité : un plan de vol semé linéairement = un arbre initial dont les priorités reproduisent la séquence.

**Groupe de tâches prêt (à ajouter au plan APRÈS le run nocturne, sur ton go — format maison, ~8 tâches) :**

- [ ] ASG1 — Modèle `AssumptionNode` (company FK, classe, énoncé FR, S/R, tags saison, parent + liens d'invalidation, α/β + α₀/β₀, H, last_tested_at, statut assumed/testing/validated/stale/retired) + migration. **Done =** CRUD scopé société, contraintes de classe testées. Files: `apps/adsengine/models.py` (+migration), tests. (SCHEMA) (@lane: backend/adsengine-core) (@model: sonnet)
- [ ] ASG2 — Évolution hebdo des posteriors (Celery) : oubli ρ=0,5^(1/H) vers le prior, par classe ; tags saisonniers = posteriors par saison, jamais d'oubli saisonnier. **Done =** tests dorés reproduisant §3.2 (regonflement exact sous seed). Files: `apps/adsengine/assumption_decay.py`, tasks.py, tests. (ROUTINE) (@model: sonnet)
- [ ] ASG3 — Scoreur VoI + ordonnanceur : **S×U×R×T/C** avec U=1−|2·P(meilleur)−1| recalculé hebdo depuis le posterior oublié (at-science §A.3/§B.4) et T=clip(δ_plausible/δ_MDE,0,1) branché sur ADSENG13 ; argmax à l'ouverture d'un slot ; DecisionLog obligatoire. Remplace la transition fixe d'ADSENG35 derrière un flag. **Done =** tests dorés : un nœud périmé re-surface par U seul ; un nœud intestable (T≈0) ne gagne jamais la file. Files: `apps/adsengine/voi.py`, tests. (ARCH) (@model: opus)
- [ ] ASG4 — Cascade d'invalidation : bascule d'un parent ⇒ enfants stale + alerte 🔵 ; jamais de re-test auto d'un enfant sans passer par la file VoI. **Done =** cascade testée sur un arbre à 3 niveaux, aucun test auto déclenché. Files: `apps/adsengine/assumption_graph.py`, tests. (ROUTINE) (@model: sonnet)
- [ ] ASG5 — Format de semis YAML + validateur (le contrat IA du §4) : import idempotent, préflight (checks ADSENG38 étendus : arbre ≥N nœuds testables, backlog compatible). **Done =** un semis invalide refusé avec raisons FR ; double import = même état. Files: `apps/adsengine/seeding.py`, docs/engine/seed-format.md, tests. (ARCH) (@model: sonnet)
- [ ] ASG6 — Écran « L'Arbre » : la vue plan-vivant (nœuds par statut/fraîcheur, file VoI, historique = l'arbre à travers le temps — TON « the tree is the plan history » à l'écran). **Done =** RTL, chiffres = API, drill-down nœud→tests→leads. Files: `frontend/src/features/adsengine/TreeScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine) (@model: sonnet)
- [ ] ASG7 — Scénarios de simulation ordonnanceur (ADSENG36 étendu) : péremption→retest auto, saison qui revient, cascade d'invalidation, famine de testabilité (l'arbre veut tester un barreau intestable → propose à l'humain au lieu de brûler le slot). **Done =** 4 scénarios verts en CI, déterministes sous seed. Files: `apps/adsengine/simulator.py` (extension), tests. (ARCH) (@model: opus)
- [ ] ASG8 — Priors hiérarchiques INTRA-tenant (le pattern Amazon KDD 2024 / AISTATS 2022) : un nœud neuf du vertical agricole hérite des agrégats résidentiel/catégorie, κ_max=min(50, 1 sem) ; jamais cross-tenant (§6). **Done =** un nœud neuf converge vers sa donnée locale en ~1 semaine simulée ; l'héritage ne traverse jamais une frontière de company (test d'invariant). Files: `apps/adsengine/priors.py`, tests. (ARCH) (@model: opus)

GATED (inchangé) : benchmarks cross-tenant (§6), commentaire LLM, publication organique.

---

## 6. Cross-tenant : le verdict compliance (net)

- **Intra-tenant, cross-catégorie (résidentiel↔agricole↔B2B de Taqinor, puis de CHAQUE client sur SES campagnes)** : légal aujourd'hui (« internal business purposes » Meta), pattern publié (Amazon KDD 2024, −12,7% CPC), **à construire (ASG8)**.
- **Cross-tenant (le modèle Varos/Triple Whale)** : les Advertising Standards de Meta interdisent le commingling multi-annonceurs, l'exception « aggregate and anonymous » vise TES campagnes (singulier), et les Business Tools Terms interdisent la divulgation des rapports à des tiers sans accord écrit Meta. Varos/Triple Whale/Databox opèrent depuis des années sans sanction — c'est « tout le monde le fait et personne n'est poursuivi », PAS « les conditions le permettent ». En plus : leurs planchers de cohorte (≥5–15 comptes) sont hors de portée avant des années. **Reste GATED**, avec le schéma consent-gated (opt-in contribution, egress agrégé seulement, plancher de cohorte) documenté pour le jour où le produit a assez de clients.
- **Priors de démarrage publics** : LocaliQ 2025 (Landscaping CPL $117,92 ; Roofing $228,15), WordStream 2026 (Home Improvement $90,92) — benchmarks SEARCH Google, pas Meta CTWA : ordre de grandeur au mieux, jamais un prior branché. Pas de catégorie solaire publiée.

---

## 7. Réponse à « jusqu'où l'automatisation »

**Plafond atteignable avec l'arbre : des mois — 6, 12, 24 — d'exécution sans IA**, bornés par trois choses seulement : (1) le backlog créatif s'épuise (recharge trimestrielle — humain/IA) ; (2) l'arbre bute sur un nœud intestable à ton volume (arbitrage trimestriel) ; (3) le monde change hors-cadre (nouveau produit, nouvelle loi — la watchtower alerte, l'humain décide). Le moteur, lui, choisit, teste, lit, bascule, retire, re-teste, alloue, pace, garde et journalise — seul. Ton énoncé « l'IA donne les grandes directions une fois au début, au pire trimestriellement » est exactement le contrat du §4 — pas un compromis, le design.

---

## 8. Ce qui n'est PAS résolu (les vrais restes)

1. Les demi-vies (8/13/26 sem) sont des défauts raisonnés depuis l'évidence de décroissance — pas des constantes de la nature. ADSENG37 (tests terrain) doit les calibrer sur TES données après 2-3 trimestres.
2. Le barreau signature reste statistiquement noir à 100 MAD/j — aucun arbre ne change ça ; seul le volume (budget) ou le temps l'éclaire.
3. La détection de « dérive du pays/l'humeur » hors saisons connues = le détecteur de divergence + les anomalies SMB — réactif, pas prédictif. Personne n'a mieux à ce budget.
4. Un faux chiffre attrapé pendant la recherche (une « courbe de décroissance Meta à 10 jours » inventée par un résumé de moteur de recherche) — rappel : les demi-vies rondes et confiantes se méfient.

---

# EXTENSION (17/07, round 2) — Autonomie totale : campagne perpétuelle, génération automatique, multi-signaux

Sources : `fa-perpetual`, `fa-autogen`, `fa-signals`, `fa-guardrails` (scratchpad session, à committer avec ce dossier).

## 9. La campagne perpétuelle — elle existe, et Meta la récompense

**Verdict : oui, la campagne perpétuelle existe — et c'est même la direction que Meta pousse structurellement.** Le framework Performance-5 de Meta nomme la « simplification de compte » pilier n°1, et l'ère Andromeda recommande MOINS de campagnes, plus longévives (1-3 ad sets max), parce que chaque restructuration reset l'apprentissage [VÉRIFIÉ]. Preuves de longévité : une pub Mejuri documentée à 431 jours consécutifs ; l'heuristique praticienne récurrente « 30-90+ jours de run continu = rentable » ; et notre propre trouvaille — la pub Tecas active depuis nov. 2024, 20+ mois (constat interne antérieur, non re-vérifié ce round). Pour le lead-gen local, l'always-on est le défaut tellement évident que personne ne prend la peine de l'argumenter [NON VÉRIFIÉ, consensus].
**La nuance qui structure tout : l'ARCHITECTURE est perpétuelle, les CONTENUS pourrissent.** Les créatifs s'usent en ~2-3 mois ; le conteneur vit des années. Seul choc documenté ayant forcé des restructurations massives : iOS14/ATT (avril 2021, -38% de ROAS mesuré).
**Réponse à « quelle longueur ? » : indéfinie par construction.** Notre moteur EST déjà la bonne forme : un conteneur ABO permanent, 2-4 bras créatifs gérés par le bandit, rotation phasée, l'arbre qui re-teste ce qui périme. (Garde-fou : les 15-50 créatifs/ad set des blogs Andromeda 2026 = ecommerce à gros volume ; à 100 MAD/j notre MDE plafonne à 2-4 bras.)

## 10. Génération automatique — l'évidence, puis la ligne

**Le fait central [VÉRIFIÉ] : AUCUN vendeur en 2026 ne publie des pubs sans revue humaine par défaut** (AdCreative, Pencil, Omneky, Creatify, HeyGen, Arcads — génération auto, porte humaine partout). Le SEUL généré-sans-revue par défaut : la couche Advantage+ Creative de Meta — exactement là où s'accumulent les incidents publics (vélo à deux guidons REI, swaps IA Snag Tights, True Classic). Les conditions GenAI de Meta mettent 100% de la responsabilité sur l'annonceur, même quand c'est l'algo de Meta qui a modifié la créa [VÉRIFIÉ, primaire]. La FTC (oct. 2024) interdit les témoignages fabriqués par IA à 51 744 $/infraction — le Palier C est du droit, plus seulement de la marque [VÉRIFIÉ]. Meta punit les MOTIFS de désapprobation (reach réduit, CPM majoré, restriction) — et une pub désapprouvée n'a droit qu'à UN appel [VÉRIFIÉ]. Bonne nouvelle : PERSONNE ne vérifie les chiffres générés contre une base — notre checked-facts machinisé est EN AVANCE sur la pratique.

### 10.1 Les trois paliers
- **Palier A — automatique jour 1** : variantes texte/statiques dont CHAQUE chiffre vient de la table de faits verrouillée + linter ; recombinaisons de composants approuvés ; swaps de faits whitelistés sur gabarits validés.
- **Palier B — généré seul, regardé 10 min/semaine** : angles/hooks NEUFS, vidéos explainer — lot hebdo. Graduable en A après N semaines propres (toggle par capacité). Calibration honnête (précédent SEO programmatique : 100% de revue sur les ~3 premiers lots d'un gabarit neuf) : la plupart des angles neufs restent en B longtemps.
- **Palier C — jamais** : chantiers/clients/témoignages réels de Taqinor ; tout chiffre hors table. Adossé FTC.

### 10.2 La pile de sécurité (ordre de construction)
1. Génération ANCRÉE sur la table de faits (citations par claim). 2. Whitelist numérique dure (regex+NER, zéro palier mou). 3. Filet de véracité non-numérique (scoreurs groundedness type HHEM/Lynx). 4. Pré-linter policy/marque FR (UN seul appel par pub). 5. Rayon d'explosion : née PAUSED → budget test fixe → auto-pause maison sur désapprobation/négatifs (Meta n'en offre AUCUN — vérifié comme absence — à construire via polling + Ad Rules Engine). 6. Audit/rollback : version table de faits, verdicts par claim, décisions, statuts Meta, id du bras — rollback = pause + décote posterior + quarantaine gabarit. 7. Drapeau : des pubs FINANCEMENT déclencheraient la catégorie spéciale « Financial Products » (ciblage large forcé) [VÉRIFIÉ].

## 11. Multi-signaux — ton idée, confirmée puis affûtée

**Ta structure 3 couches = ce que fait l'industrie** : l'enchère Meta elle-même est un composite à poids fixes (Total Value = Bid × Estimated Action Rate + Ad Quality) ; le métier résout « plusieurs signaux » par écrasement scalaire, jamais multi-objectifs [VÉRIFIÉ]. **Apprendre les poids à notre n = fiction, avec reçus** : le surrogate index (Athey/Chetty) a demandé 200 expériences / 1 098 bras chez Netflix et ratait encore 21-35% des bons lancements ; nous : ~150 leads, 3-9 signatures/trimestre → poids FIXES revus trimestriellement [VÉRIFIÉ]. **Le composite reste HORS de l'optimiseur** (Goodhart : poids CTR → clickbait ; poids conversations → curieux) — affichage + alerte seulement.
**Trois affûtages** : (1) quadrant de garde-fous durs (fréquence, quality_ranking, CPL, qualité de compte) qui ne fait QUE freiner ; (2) DEUX scores de santé (créatif vs opérations) pour qu'une vente lente ne salisse jamais l'allocation créative ; (3) filigrane de cohorte (chaque signal ancré date d'impression, intégré à maturation : proxy 7 j → CPL 14-28 j → signature 60-90 j, poids renormalisés).
Réalités API [VÉRIFIÉ] : diagnostics de pertinence = 35 j, ordinaux, ≥500 impr — drapeau, jamais récompense ; quality_ranking = le proxy négatif utilisable ; la signature ne peut PAS être un événement CAPI CTWA (fenêtre 7 j) — la vérité argent reste un veto humain.

## 12. TOUTES les tâches vers l'autonomie totale

**Sur main, en construction cette nuit** : ENG1-31 + ADSENG1-53. **Prêts, à ajouter au plan sur ton go** :
- **ASG1-8** (§5) — l'arbre vivant.
- **AGEN1-10 — génération autonome** : AGEN1 FactTable versionné/société ; AGEN2 génération ancrée (citations, seed-brief « quelques mots ») ; AGEN3 vérificateur whitelist regex+NER ; AGEN4 filet groundedness ; AGEN5 pré-linter FR ; AGEN6 routeur paliers A/B/C + toggles graduation (pattern ENG8) ; AGEN7 chaîne vidéo auto (JSON2Video/ElevenLabs → CreativeAsset pending) ; AGEN8 rayon d'explosion + auto-pause maison ; AGEN9 audit/rollback + quarantaine ; AGEN10 scénarios sim génération (lot sale → bloqué ; graduation propre → passe). Opus : AGEN2/3/8 ; sonnet le reste.
- **SIG1-4 — signaux** : SIG1 deux scores de santé (poids fixes en config) ; SIG2 quadrant durs (freine seulement) ; SIG3 filigranes de cohorte ; SIG4 affichage console. Opus : SIG2.
**Reste humain pour toujours** : unpause, plafonds, Palier C, le semis trimestriel, le veto argent. **Total : ENG 31 + ADSENG 53 + ASG 8 + AGEN 10 + SIG 4 = 106 tâches**, dont 84 en construction cette nuit.
