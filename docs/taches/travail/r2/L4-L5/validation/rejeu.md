# R3 — lentille « rejeu » : la session des 19-20/11 rejouée contre le projet go-deep L4/L5

Vérificateur neuf, lecture seule. Lu : PLAN-L3, RETRO, ETAT, vague3-ajouts, tout `projet/` ; grep : vague4, tour1/tour2 consolidation, tour4.
Exécuté dans cette session : la sonde `regime.md` sur 2 commits et 6 mots ; le crochet de `crochet.md` sur les 4 demandes
réelles ; l'outil d'usage `mcp__ccd_session_mgmt__get_usage`. NON exécuté : `plan_lanes.py`, le script du registre.

## Verdict
Le projet garde les dix réussites et met un vrai mécanisme sur 5 des 10 coûts (contrat de sortie, disjoncteur, contrat
global seul, outillage, état sur disque). Mais rejoué à la lettre il fait PIRE sur deux points : l'orchestrateur devient
le copiste du registre (§ 6.8 aggravé) et la règle de quota aurait supprimé la vérification finale qui a trouvé les 2
bloquants. La sonde de régime se trompe sur 2 des 4 demandes réelles. L5 n'ajoute que deux capacités qui auraient changé
cette session.

## 1. Rétro § 6 (coûts) — empêché ?
| # | Mécanisme du projet (citation) | Jugement |
|---|---|---|
| 1 classe ×4 | SKILL étape 2 « a root behaviour behind ≥ 2 findings gets `fiche-invariant.md` with the grepped list of EVERY place » | mécanisme partiel : la liste est GREPPÉE sur du code, or la classe varie par CONDITION (voir § 2a) → **important I1** |
| 2 coutures | étape 5 « ONE seam lane alone… » ; consolidation § 4.3 « Interfaces écrites noir sur blanc » | ce que la session faisait déjà (vague3-ajouts, lane de couture) et qui a rendu des coutures à chaque vague : intention sans mécanisme neuf → **I3** |
| 3 400→409 | étape 3 « A global contract change goes ALONE, first… Found by CI mid-wave: no new lane starts » | règle juste, déclencheur trop tardif (§ 2b) → **I2** |
| 4 poste ≠ CI | instrument § 3 « Pièges connus (les vérifier au tour 0) » | liste sans commande de vérification ; optionnel |
| 5 cibles | contrat § 1 « Un critère sans mesure exécutable n'est pas un critère » | mécanisme oui, mais le script de mesures DOM n'existe nulle part (notes § 7 : « tâches [ ] futures ») → **I8** |
| 6 mesure | K7/K8 paires + DOM | même dépendance que 5 |
| 7 coût | Guardrails « k = floor((90 − u − 5) / 25) » | formule incohérente avec le nombre de tours → **B2** |
| 8 goulot | registre § 1 « `evenements.jsonl` — écrit par l'orchestrateur SEUL… il recopie les sorties » | AGGRAVE → **B1** |
| 9 vrai appareil | L4 : rien (dit au rapport) ; L5 étape 4 | dépend du temps de Reda ; un moteur Safari disponible est ignoré → **I10** |
| 10 outillage | « worktrees launched ONE per message », `cmd /c rmdir`, `DB_CONN_MAX_AGE=0`, scratchpad | mécanisme réel ; gardé |

## Rétro § 5 (réussites) — gardé ?
1 écran réel + preuve : brief-relecteur règle 3 « Chaque constat est PROUVÉ » — gardé. 2 neufs, l'auteur ne valide pas :
registre « `par` (relecteur NEUF, jamais l'auteur) » — gardé. 3 rôles × axes + références : brief-relecteur « UN seul de
chaque », « tu compares à ELLES » — gardé. 4 table fichier → lane : REMPLACÉE par « aucune table fichier → lane écrite à
la main » (consolidation § 4.2) au profit de `plan_lanes.py`, jamais essayé sur 100 corrections d'un coup → **I11**.
5 fichier de restes : « cross-lane requests become rows » mais aucune étape du registre ne les accepte (listes FERMÉES :
consolidation, test-premier, correction, contre-verification, disjoncteur, rejeu) et `etat.md` renvoie à un état
« `reste` » qui n'existe pas → **I6**. 6 couture : gardé. 7 classes : gardé (avec I1). 8 choix par règle : Tensions 3 —
gardé. 9 éclaireur haiku : étape 6 — gardé. 10 état sur disque : points de contrôle + `etat.md` « Prochaine action
unique » — gardé et amélioré.

## 2. Trois moments rejoués
**(a) La classe « une frappe se perd ».** Au tour 1 la consolidation avait déjà ≥ 2 constats : R2-001 (taper vite après
« Ajouter »), le 2e chiffre de l'heure perdu (`ui/SelecteurQuand.jsx`), R2-044 (notes perdues au rechargement) → la fiche
aurait été ouverte au tour 1. Ses suites : tour 2 R3-060 « Échap ferme le panneau et perd l'heure tapée » ; vague 3 lettre
avalée après le choix d'un projet (valeur périmée) ; vague 4 R4-22 hors ligne ; VERIF « Première action » perdue à
« Terminer » sans Entrée. Avec la fiche telle qu'écrite : la lane cherche `git grep "<motif>"` ; un motif (« setState
après await ») attrape la vague 3, pas le hors-ligne (file d'envoi) ni « Terminer »/Échap (fermeture sans valider) — trois
mécanismes différents, un seul invariant. Rien ne force la liste des CONDITIONS ; la ligne « ce que le grep ne voit pas »
est un champ libre. Ce qui l'aurait forcé : une matrice champ × condition (réseau lent, hors ligne, après une suggestion,
fermeture par Échap / Terminer / retour / balayage, rechargement, iOS tue l'appli) dans la fiche, un test de classe qui
l'itère, et la classe donnée au relecteur du tour suivant comme cible. Avec elle, « Terminer » et Échap tombaient d'un coup
dès le tour 1 ou 2 ; le hors-ligne très probablement.
**(b) 400 → 409.** Le changement n'était PAS visible à la consolidation du tour 1 : api-fuzz ne lisait pas le module (compte
de fuzz en 403 jusqu'à TCH168, `vague3-ajouts.md`). La branche « empêché s'il est vu à la consolidation » ne s'applique
donc pas ; reste « no new lane starts until it lands », qui n'arrête pas les lanes déjà en vol (vague 3 tournait). La
session avait même écrit la table (vague3-ajouts « Table des réponses passées de 400 à 409 ») et le coût est venu du
partage serveur (lane CI) / lecteurs (L2 `tachesApi.js`, mocks, e2e) : la critique du tour 4 § 7 trouve encore des écrans
en toast. Le projet ne change aucun de ces deux faits.
**(c) Quota.** Formule : 6 % → floor(79/25) = 3 ; 35 % → 2 ; 50 % → 1 ; 71 % → 0 (et « No new round when u ≥ 65 »).
Lisible : l'outil existe et répond — essayé ici : « Weekly · all models 82 % », « Weekly · Fable 70 % », plus le contexte
de la session (96 %). Le quota au début du tour 3 n'est écrit dans aucune pièce (seul « 71 % le 19/11 au soir », pendant
la vague 4) : je ne peux pas dire si la formule l'aurait permis ; s'il partait sous 65 %, oui. Deux défauts : (1) « 3
rounds + final » (SKILL tableau) contre « <k> (≤ 3 en L4) + le dernier tour avant le merge » (contrat § 2) : à 6 % on
planifie 3 tours + un dernier tour + final ≈ 4 × 25 + 5 = 105 points pour 84 disponibles ; (2) l'étape 10 rattache la
vérification finale au dernier tour (« The last round adds ONE fresh targeted verification ») : à 71 %, « no new round »
interdit ce tour, donc la VERIF et la critique — qui ont trouvé 2 bloquants et 7 corrections serveur — n'ont pas lieu.

## 3. Sonde de régime appliquée à la lettre (git fetch 8,0 s ; chaque signal < 1 s ; promesses non chronométrées)
| Demande | Commandes (m) | Signaux | Sonde | Juste ? |
|---|---|---|---|---|
| « build my own project/task manager » (17/11) | parent de TCH4 `381e11e27`, m = taches | F 0, plan PLAN_TACHES 4 [x] / 170, OWN 1 | P ≈ 0 mais 1 seul signal FORT absent → ni NEUF (« ≥ 2 absents »), ni EXISTANT, ni MIXTE (P < 20) : **trou** | non (NEUF) |
| idem, avant TCH1 | m = task / tasks / project | tout 0, MAP 2-4 | NEUF | oui ; mais m n'est pas dans la demande anglaise |
| « look at what was done, and redo… » | m = taches sur origin/main | F 344, plan 200/0 | EXISTANT | oui ; m vient du contexte, et P se calcule sur quelles promesses ? (la demande n'en porte pas) |
| « cant we have our own widget on iphone ? » | m = widget, iphone | F 0, plan 0, OWN 0, MAP 0/1 | NEUF par les signaux ; la parade « F = 0 mais MAP > 0 » ne part pas | non : `git grep widget` trouve `features/taches/iphone/scriptTuile.js` (tuile) → MIXTE |
| « lets learn… make it an L4 or l5 » | m = go-deep / methode | F 0 (la sonde ne regarde que `apps/`, `features|pages/`) | NEUF | non : `.claude/skills/go-deep/SKILL.md` existe → EXISTANT/MIXTE ; et « maquettes, PACT10, plan run » n'ont pas de sens pour une méthode |
Crochet projeté, rejoué sur ces 4 textes : L3 pour la 4e (« go L3 on this » ; « make it an L4 or l5 » ne part pas), rien
pour les 3 autres → auto-pick. Correct.

## 4. L5 : plus puissant ou plus cher ?
1 Figer — aurait attrapé en CI les régressions R3-060 (Échap, régression de R2-041) et R3-120 (Semaine illisible) au lieu
du tour 2 ; mais L4 EXISTANT fige déjà les CHIFFRES, et la session avait sa « Garde de non-régression » (tour2 § L1). Gain
réel sur les GESTES. 2 Chapman — n'aurait rien changé (« never decide on it alone »). 3 Juges indépendants — ancrage sur
« ~20 cas que Reda a notés » et autre famille « avec le oui de Reda » : inapplicable sous « aucune question » ; rien changé.
4 Vraie vie — la seule qui attaque ce que rien n'a vu (ETAT « Rien n'a été vu sur un vrai iPhone »), mais entièrement à la
charge de Reda. 5 Composer — pass^3 aurait pris la lettre avalée « verte sur le poste, ROUGE en CI » avant la CI ; garde
rouge sur l'origine : utile. 6 Revalider le harnais — rien pour une session à un modèle.
Manque à L5 pour mériter son nom, sans Reda : un passage WebKit (moteur de Safari) — installé sur ce poste
(`ms-playwright/webkit-2311`) alors que `frontend/playwright.config.js` note « aucun moteur WebKit » ; une semaine SIMULÉE
(horloge avancée jour par jour sur un compte semé, boucle quotidienne rejouée 7 fois) ; après le deploy de Reda, la
lecture prod déjà autorisée (mémoire `prod-read-access`) des erreurs et de l'usage du module.

## 5. Utilisabilité
Par où commencer : la section Regime d'abord, claire. Pour L4, l'étape 0 est une phrase de 7 actions sur 5 gabarits, et la
ligne de coût est 80 lignes plus bas (Guardrails) : il manque une liste « tour 0 » ordonnée. Contradictions : registre
« orchestrateur SEUL » contre consolidation « Sorties : (1) les événements `consolidation` au registre » ; brief-relecteur
« Écris chaque verdict dans ton rapport ; l'orchestrateur le reporte » ; étape 10 mêle merge par tour et fin (« release
claims after it; tear the instrument down ») ; SKILL cite `conception.md` (le fichier s'appelle `notes-de-conception.md` ;
la PR § 7.3 le renomme — à faire). Restes du module Tâches : brief-lane § 5.7 (« Une frappe ne se perd JAMAIS… valeur
COURANTE »), instrument « journée d'exemple datée du jour », « une carte liée à l'heure », brief-relecteur rôles « boucle
quotidienne | planification | premier jour », contrat K7 « 1re ligne utile », registre exemple « frappe-perdue », regime
§ 2 table — acceptables comme EXEMPLES s'ils sont marqués comme tels. Les outils de l'instrument (`capturer-reel.cjs`,
`semer_compte.py`, `reinit-compte.sh`, `lancer-django.sh`, `pile-locale.md`) ne sont PAS sur `origin/main`
(`git ls-tree origin/main docs/taches/travail/r2/` vide) et aucun gabarit ne les cite.

## Constats et corrections
**B1 bloquant — registre copié à la main par l'orchestrateur.** Tour 1 = 152 + 102 événements, tour 2 = 191 verdicts,
retranscrits de la prose : le goulot § 6.8 grossit. Correction `registre.md` § 1 : « un écrivain par FICHIER :
`evenements/T<n>-consolidation.jsonl` (consolidation), `evenements/T<n>-L<k>.jsonl` (chaque lane, dans le dossier de
notes), `evenements/T<n>-<code>-cv.jsonl` (chaque relecteur, contre-vérification), `evenements/T<n>-orchestrateur.jsonl`
(rejeu, disjoncteur) » ; script § 5 : `for f in glob.glob('evenements/*.jsonl')` ; brief-relecteur « Tour 2 » 1 :
« écris chaque verdict dans ton fichier d'événements » ; brief-lane § 7 : idem.
**B2 bloquant — la règle de quota supprime la vérification finale et sur-planifie.** Correction Guardrails + contrat § 2 :
« k compte TOUS les tours de relecteurs, dernier tour compris (≤ 3) ; la vérification ciblée finale et la critique du diff
ne sont PAS un tour : 10 points réservés, toujours joués avant le merge, jamais coupés par le seuil de 65 % ; k =
floor((90 − u − 10) / c), c = 25 au départ puis le coût mesuré du tour 1 (écrit à l'état) ». Étape 10 : détacher la
vérification du « last round ».
**I1 — fiche d'invariant sans conditions.** `fiche-invariant.md` : ajouter « Matrice champ × condition (réseau lent, hors
ligne, après une suggestion, fermeture sans valider : Échap / bouton de fin / retour / balayage, rechargement, appli tuée) ;
la garde itère la matrice » ; brief-relecteur tour ≥ 2 : « attaque chaque classe ouverte sur sa matrice ». Remplacer
brief-lane § 5.7 par un renvoi aux fiches de classe du run.
**I2 — contrat global détecté trop tard.** SKILL étape 0 + étape 6 : « PR brouillon AU TOUR 0, sur la tête intacte ; lire
chaque job contre le périmètre (la garde lit-elle le module ? compte de fuzz avec droit ? version d'axe) ; ses rouges
forment la Lane 0 avant le tour 1 ». Étape 3 : « la Lane 0 possède le serveur ET tous ses lecteurs trouvés par grep
(client d'API, mocks, specs e2e), même dans les fichiers d'autres lanes ; les lanes en vol reçoivent la table et se
rebasent ».
**I3 — coutures.** consolidation § 4.3 : « table des identifiants partagés (classe CSS, prop, `data-*`, code HTTP,
événement) avec leur propriétaire ; la lane de couture commence par grepper chacun des deux côtés ».
**I4 — lecture du quota.** Guardrails : remplacer « untried » par « `mcp__ccd_session_mgmt__get_usage` (outil différé :
ToolSearch) ; lire `Weekly · all models` (et `Weekly · Fable` pour un orchestrateur Fable) ; `context.percentUsed` ≥ 70 % →
écrire l'état et prévoir la reprise ».
**I5 — sonde de régime.** `regime.md` § 3 : « NEUF si P < 20 % et F = 0 (un plan dont seules des tâches de dépôt sont
cochées compte comme absent) » ; § 2 : signal `ALL=$(printf '%s\n' "$T" | grep -ci "$m")` sur tout l'arbre (`.claude/`,
`scripts/`, `apps/web/`, `docs/`) + `git grep -il` sur le mot ET ses synonymes fr/en (widget/tuile, task/tâche) ; § 3.1 :
« amélioration : les promesses sont celles de la demande d'origine du module (état des lieux) » ; § 6 : un régime
« méthode / outil » (skill, script, CI) = MIXTE sur le fichier hôte, preuve = rejeu d'un run passé, sans maquette.
**I6 — demandes croisées sans ligne.** registre § 3 : étape `demande-croisee`, verdicts `ouverte` · `faite` · `refusee`,
champs `de`, `vers`, `fichier`, `changement` ; etat.md « Restes » : renvoyer à ces lignes.
**I7 — test-writer sans brief.** Ajouter à brief-lane une section « Test premier » (modèle sonnet, un par lane, dans le
worktree de la lane sur `tests/T<n>-<lane>`, seulement classes + A perte de données / chiffre faux, avant la lane).
**I8 — instrument sans outils.** instrument § 2 : citer les sources de départ `git show <sha>:docs/taches/travail/r2/
{capturer-reel.cjs,semer_compte.py,reinit-compte.sh,lancer-django.sh,pile-locale.md}` (ou les copier sous `gabarits/`) ;
le script de mesures DOM s'écrit au tour 0 et tourne sur le commit intact (base des K7).
**I9 — merge par tour sur un module en prod.** Tour 1 aurait mis sur `main` 3 régressions et 37 demi-corrections. Étape
10 : « EXISTANT avec utilisateurs : la ligne de merge dit à Reda « ne déploie qu'après la contre-vérification du tour
suivant » ; toute régression trouvée passe « avant le merge » du tour suivant ».
**I10 — L5.** Ajouter « WebKit : les relecteurs iPhone rejouent aussi sous le moteur WebKit de Playwright » (en L4 si
installé), « semaine simulée par horloge » et « lecture prod après deploy » ; retirer ou marquer « sans effet en session
unique » Chapman et la revalidation.
**I11 — plan_lanes.py sans repli.** consolidation § 4.2 : « si la sortie unit tout en une lane surdimensionnée ou refuse
des tâches, la table fichier → lane de la consolidation sert de repli, dite au rapport » (non vérifié ici : je n'ai pas
lancé `plan_lanes.py`).
Optionnels : liste « tour 0 » en tête de L4 ; « exemple » sur les restes Tâches ; 102 corrections > plafond ~100 (Tensions 2).
