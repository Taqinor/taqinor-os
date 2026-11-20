# Notes de conception — go-deep L4 « ship-grade » et L5 « all the way » (R2, 20/11/2026)

Concepteur : R2 du L3 `PLAN-L3.md`. Entrées lues en entier : `PLAN-L3.md` (14 orientations, tensions), `RETRO-METHODE.md`,
les six rapports `recherche/{A,B,C,D,E,F}`, la skill actuelle, `.claude/settings.json`, `CLAUDE.md`, `qa-explorer`
(structure STEP 0-9), `METHODE.md` (§C.4, §E), les gabarits r2 (`brief-revue`, `brief-lane`, `pile-locale`, `ETAT`,
`vague4`, structure de `tour2/consolidation`). Sigles de source : `R§n` = rétro § n ; `A§n` … `F§n` = rapport de
recherche et section ; `O<n>` = orientation n° n du Journal de `PLAN-L3.md`.
Vérifié dans cette session : skill et `settings.json` du worktree identiques à `origin/main` (fins de ligne mises à
part) ; sonde de régime exécutée sur `origin/main` (`gabarits/regime.md` § 2) ; crochet testé sur 31 phrases + 7 à
retour à la ligne (`crochet.md`) ; script de courbe du registre exécuté sur l'exemple (`gabarits/registre.md` § 5).
NON vérifié : tout ce qui demande un run réel (§ 6).
Taille : `SKILL.md` = 239 lignes (objectif 220 dépassé de ≈ 19 : les deux tableaux tiennent une ligne par rangée mais
la doctrine L1-L3 d'origine est gardée telle quelle ; tout le procédural est dans les 9 gabarits).

## 1. La session du 19-20/11 rejouée avec L4 tel qu'écrit (rétro § 6)
| # | Ce qui a coûté (R§6) | Avec L4 | Mécanisme |
|---|---|---|---|
| 1 | Même classe revenue 4 fois (frappe perdue) | **réduit** | consolidation qui NOMME la classe dès 2 constats + fiche d'invariant avec la liste GREPPÉE des endroits violables (la lane corrige la liste, pas le symptôme) + test de classe écrit par un autre et en lecture seule (étapes 2, 4, 11). Pas « empêché » : un grep peut manquer une façon d'écrire le geste (la fiche a une ligne « ce que le grep ne voit pas »). |
| 2 | Coutures entre lanes (classe CSS, bouton caché, titre qui recouvre, tests sur l'ancien code HTTP) | **réduit** | lane de couture seule gardée ; contrat global SEUL d'abord ; interfaces écrites + `@after` dans le plan ; specs e2e rejouées sur le build assemblé. Le couplage de COMPORTEMENT reste (A§3 : Anthropic ne le règle pas non plus). |
| 3 | Changement transversal tardif (400 → 409, 5 allers-retours CI) | **empêché** s'il est vu à la consolidation (Lane 0 seule, verte avant la vague) ; **réduit** s'il naît d'un rouge CI en cours de vague (aucune nouvelle lane ne part avant qu'il soit plié). |
| 4 | Poste ≠ CI (lock, horloge, compte de démo, fuseaux, axe) | **réduit** | pièges listés et vérifiés au tour 0 (`instrument-de-revue.md` § 3) ; toute preuve dépendant d'une version se lit contre la CI ; lanes sans gate local (WOW23). L'écart d'horloge et de fuseaux reste. |
| 5 | Cibles jamais atteintes (« ≤ 260 pt ») | **empêché** | contrat de sortie chiffré au tour 0 ; une cible hors contrat ne bloque pas, une cible dans le contrat se mesure à chaque tour par le même script DOM. |
| 6 | Pas de mesure objective avant le tour 3 | **réduit** | mesures DOM et jugements par paires dès le tour 1 ; courbe par relecteur et taux d'écartés tirés du registre. Aucune note absolue (E§1.6). |
| 7 | Coût (16 relecteurs opus, 40 lanes, captures relues, re-semis, front reconstruit, orchestrateur Fable) | **réduit, non chiffré** | ligne de coût + plafond de tours calculé sur le quota ; contre-vérification échantillonnée sous 10 % de non-réglé ; galerie du tour 0 ; orchestrateur opus. Le gain n'est pas mesurable avant un run. |
| 8 | Orchestrateur goulot (90 % de contexte) | **réduit** | registre machine (seule chose relue), messages de 15 lignes, lanes par `plan_lanes.py`, éclaireur haiku pour la CI, points de contrôle sur disque. L'agent « plieur » n'est PAS imposé (B§3 contradiction 2) : à essayer sur une vague. |
| 9 | Rien sur un vrai appareil ni une vraie semaine | **inchangé** en L4 (dit au rapport) ; **traité** en L5 (étage « vraie vie »). |
| 10 | Pannes d'outillage (agents isolés lancés ensemble, `worktree remove` sur jonction, Postgres saturé, fichier temporaire hors arbre) | **réduit** | une lane isolée par message ; `cmd /c rmdir` de la jonction d'abord ; `DB_CONN_MAX_AGE=0` ; temporaires dans le scratchpad. La saturation du Postgres partagé dépend de l'autre session. |
| — | Ce qui a marché (R§5, 10 points) | **gardé** | 1 écran réel + preuve ; 2 relecteurs neufs, l'auteur ne valide pas ; 3 rôles × axes + références nommées ; 4 consolidation contre le code (lanes par `plan_lanes.py` au lieu de la table à la main) ; 5 restes → lignes de registre ; 6 couture ; 7 sujets récurrents = classes ; 8 choix par règle écrite ; 9 éclaireur haiku ; 10 état sur disque. |
| — | Un PR de 246 fichiers ouvert ≈ 2 jours | **changé** | merge par tour dès la CI verte (Tensions 2) + critique du diff serveur à chaque merge. |

## 2. Ce que L5 aurait ajouté à cette session
- **Figer avant de toucher** : des goldens des chiffres servis (charge du jour, progression, rythme) enregistrés sur le
  commit intact auraient rendu ROUGES en CI les 3 puis 2 régressions au lieu d'attendre le tour suivant (R§3), et la
  contradiction « 6 h / 2 h 15 / 1 h 30 » (vague4 R4-01) aurait été un golden à quatre lectures dès le tour 1.
- **Estimer le reste** : deux relecteurs sur les deux écrans centraux au tour 1 → une fourchette « borne basse » au
  lieu du seul calcul indicatif a posteriori (C§3 : 19-37 « avant le merge » restants, ordre de grandeur).
- **Juges indépendants** : beauté par paires aveugles contre une référence, ancrée sur ≈ 20 cas notés par Reda.
- **Étage vraie vie** : le vrai iPhone / Safari, les notifications, cinq jours d'usage — le seul étage jamais atteint (R§4).
- **Composer** : la garde « une frappe ne se perd jamais » prouvée rouge dès la 1re occurrence ; les gestes des
  relecteurs devenus specs d'acceptation rejouées à chaque vague (R§8).
- **Campagne** : le tour 4 abandonné à 71 % de quota (ETAT § 7) se serait repris dans la fenêtre suivante depuis
  l'état sur disque, au lieu d'être sacrifié.

## 3. Chaque choix et sa source
| Choix | Source |
|---|---|
| L4/L5 = niveaux de `go-deep`, gabarits en fichiers frères copiés (pas de renvoi vers la branche de notes) | F§1.1, F§1.7, F§6 ; O1 ; précédent : la skill installée `superpowers` a des fichiers `references/*.md` frères (vu sur le poste) |
| Régime lu sur `origin/main`, jamais le worktree ; annonce + SHA | D§1.3, D§4.2, D§4.7.1 ; O2 ; re-mesuré ici (`regime.md` § 2) |
| Décision par promesses servies, seuils 20 / 80 % non calibrés | D§4.3 (seuils = proposition de la lane, sans source) ; D§6 |
| Imposition par Reda, bascule en cours de route, aucune question | D§4.5, D§4.7 ; O2 |
| Cas où la règle se trompe (nom ≠ dossier, coquille parquée, plan sans coche, interrupteur, refonte → étrangleur) | D§4.7, D§2 (Fowler, résumé) ; maison `USE_PREMIUM_QUOTE_ENGINE` (D§1.7) |
| Ce que chaque régime change à chaque niveau | D§4.4 ; C§4 (figer l'existant, explorer le neuf) ; A§4 [HAR] (initialisation du neuf) ; B§4 (BMAD, Kiro « inchangé ») |
| Phrase de régime dans le brief de lane ; « ne suppose pas qu'il manque » | A§4 ([F52] propriété du code) ; B§4 (Huntley, Böckeler : recréer ce qu'on n'a pas trouvé) ; D§2 (fichier-patron) |
| Le niveau auto ne choisit jamais L4/L5, il les propose avec le coût | F§1.9, F§6 ; O1 ; METHODE §B.3 (annoncer le coût) |
| Contrat de sortie chiffré au tour 0 ; une cible hors contrat ne bloque pas | A§2 [HD] (contrat avant construction, seuil dur par critère) ; B§2 (Codex « done when ») ; C§2 (Guide Scrum) ; R§6.5 ; O3 |
| Critères K1-K12 et leurs valeurs de départ | C§5 Q3 (a)-(h) ; K4 « ≤ 1/3 » = proposition de C sans source externe (dit dans le gabarit) ; K3 ≥ 85-90 % calé sur R§3 (85 %) |
| Registre JSON Lines, ajout seulement, un écrivain par fichier | A§2 [HAR] (JSON, un seul champ modifiable) ; B§2 (Ralph `prd.json`) ; E§2 ; R§8 ; O4. « Un écrivain par fichier » = mon choix (agents parallèles) |
| `verdict_consolidation` et taux d'écartés par relecteur et par axe | B§2, B§3 contradiction 1 (CodeRabbit : 56,3 % de commentaires rejetés, préimpression) ; O4 |
| Courbe lue PAR RELECTEUR, pas en total brut | C§2, C§3 (152 → 78 → 30 = 6 / 5 / 4 relecteurs) |
| Relecteurs neufs, écran réel, preuve ; l'auteur ne valide jamais | R§5.1-2 ; A§1.1 [HD][F5] ; E§1.1-2 (Huang ; METR) |
| 4-6 relecteurs, un rôle × un axe | R§3 (6 / 5 / 4) ; D§2 (NN/g : 3-5 évaluateurs indépendants) ; A§3 [AT] (3-5) |
| Plancher = oracles et règles de qa-explorer, cités | F§2, F§4 ; O10 |
| Beauté par paires + mesures DOM, jamais une note absolue seule | E§1.6, E§2 (MLLM-as-a-Judge, UICrit : résumés) ; O7 ; écarte R§8 « notes sur 10 » comme critère principal |
| Contre-vérification avec les verdicts fermés de `vérifie` ; toutes tant que > 10 %, puis A + 25 % | F§2, F§3 C6 (taux mesurés 24 % → 15 % → 4/27) ; METHODE §C.4.2 (25 %) ; O10 |
| Classes → fiche d'invariant + liste greppée + garde rouge sur le défaut d'origine | R§6.1 ; C§5 Q4 ; C§2 (Google SRE : chaque ligne justifiée par un incident) ; B§2 (Every « composer ») ; O6 |
| Une garde par CLASSE dans une famille existante, jamais par constat | METHODE §E anti-pattern 15 (70 gardes, baselines +79 % en 7 j) |
| Lanes par `plan_lanes.py`, corrections inscrites au plan du propriétaire | F§2 (table refaite à la main), F§3 C4 ; O10 ; propriété des fichiers (CLAUDE.md, mémoire) |
| Changement de contrat global SEUL, d'abord | R§6.3 ; O11 ; CLAUDE.md PACT10 |
| Test-premier écrit par un autre, en lecture seule ; sorties « contesté / impossible » | E§2 (ImpossibleBench : tests cachés ≈ 0 triche ; option d'abandon 54 % → 9 % chez GPT-5) ; A§2 [HAR] ; O5 |
| Lanes isolées lancées une par message | F§3 C8 (mémoire du 18/11) ; R§6.10 |
| Couture seule sur l'arbre ; e2e sur le build assemblé | R§5.6, R§6.2 ; O11 |
| CI d'abord, éclaireur haiku, rouge à la lane propriétaire | R§2.7, R§5.9 ; A§2 [CC] (sorties courtes) |
| Disjoncteur par constat, 3 tentatives (au lieu des 5 tours de Superpowers) | B§2 (Superpowers `fix-loop.md` : 5 tours, 4-5 par un frais plus fort). Ramené à 3 parce qu'une de nos tentatives coûte un tour de revue entier : mon choix |
| « Sec » = deux relecteurs DIFFÉRENTS ; ne jamais viser un tour sec | C§3 (accord entre évaluateurs 5-65 %, lu-recherche) ; A§1.7 [BP] ; R§3 ; METHODE anti-pattern 1 ; O8 |
| Dernier tour « avant le merge / peut attendre » ; le reste au plan du propriétaire | R§2.9 ; METHODE §C.4.2 (écarts chez le propriétaire, jamais `ERROR_PLAN.md`) |
| Merge par tour + critique du diff serveur à chaque merge ; Fable sur la critique finale | F§3 C4, C6 ; R§4 (la critique a trouvé une régression de collage) ; CLAUDE.md MERGE FLOOR, WOW23, Model selection (a) |
| L5 figer avant de toucher | D§2 (developertoolkit, lu ; Feathers par résumé) ; C§2 (Feathers) ; O9 |
| L5 Chapman, fourchette, « borne basse » | C§1.3, C§5 Q1 (formules lues) ; C§3 (biais bas) ; O8 |
| L5 défauts semés en EXPÉRIENCE seulement | C§2 (Mills, de mémoire ; adaptation = inférence) → pas une règle |
| L5 autre famille de modèles seulement avec l'accord de Reda | E§2 (PoLL, MAD hétérogène : résumés) ; règle « pas de dépendance payante sans demander » (mémoire `user_profile`) |
| ≈ 20 cas notés par Reda pour étalonner | E§2 ; A§2 [EVAL] (20-50 tâches) |
| Étage vraie vie (30 min, 5 jours, 3 questions, drapeau, journal d'erreurs, `dataset: anon`) | C§5 Q6 (inférence de la lane) ; A§2 [MA] (testeur humain) ; F§2 (`dataset: anon`) ; O13 |
| Specs d'acceptation écrites APRÈS le constat prouvé | C§3 (Bach : pas de cas liants avant d'avoir appris le produit) ; A§2 [EVAL] |
| pass^k, k = 3 | A§2 [EVAL] (75 % par essai → ≈ 42 % sur 3) |
| Revalider le harnais à chaque modèle, un composant à la fois | A§3 [HD] ; O14 |
| Vérification par intervalles pendant les longues lanes | A§2 [F5] |
| Campagne multi-sessions, « prendre ses repères » à chaque reprise | A§2, A§6 [HAR] ; E§2 ; R§5.10 |
| Coût : 74 points mesurés, ≤ 25 points par tour | R§3 ; F§7. « ≤ 25 » = 74 / 3, borne haute (inclut tour 0, final, une part d'une autre session) : mon calcul |
| Formule k = floor((90 − u − 5) / 25), plus de tour à 65 %, arrêt à 90 % | mon choix : F§7 dit que la maison n'a aucune valeur écrite ; seuls points de données : 6 → 80 % pour 3 tours, renoncement à 71 % (ETAT § 7) |
| Ne jamais mettre de budget ni de compte à rebours dans un prompt d'agent | A§3 [F5][F52] |
| L5 ≈ 1,3-1,5 × L4 | estimation : + ≈ 25 % de relecteurs (C§2) + une lane de figeage + le temps de Reda ; non mesuré |
| Limites du poste (CPU d'abord, 1 Go par worktree, jonction, Docker) | F§7 (mémoire `machine_laptop_capacite`) ; R§6.10 |
| Sécurité de l'instrument (prod, code poussé, mail en mémoire, aucune clé, rien d'une autre session) | F§3 C1, F§5 (NON VÉRIFIÉ en r2 : `--env-file .env` sans `EMAIL_BACKEND` forcé) ; F§7 ; METHODE §A.2 ; O12 |
| Pas de L4 sans instrument (session cloud) | F§3 C3 ; CLAUDE.md 3-bis ; METHODE §C.4.7 |
| Crochet : L5 → L1, formes « go L3 », verbe obligatoire, `\n`, ignorer le collé | F§1.2, F§6 (actuel testé) ; essais de cette session (`crochet.md`) |
| Questions : lot unique en NEUF / MIXTE sans consigne ; règle écrite sinon | F§3 C5 ; METHODE §B.6 ; mémoire `founder_questions_interactive` ; B§2 (journal de décisions « coût si faux ») |

## 4. Ce que j'ai écarté des rapports, et pourquoi
- **Notes sur 10 par écran comme critère principal** (R§8, R§6.6) : forme la moins fiable selon E§1.10 ; gardées
  seulement comme paires et mesures.
- **Tour de débat entre relecteurs** : pas de gain contre beaucoup plus de calcul (E§3, MAD, résumé).
- **Auto-cohérence / vote** : de mémoire chez E (E§3), et inadapté aux constats ouverts.
- **Spec lourde (Spec Kit, Kiro) pour l'EXISTANT** : jugée trop lourde pour un petit changement et l'existant (B§3,
  Böckeler) ; gardée seulement la fiche « actuel / attendu / inchangé » (B§2) via les goldens.
- **Boucle Ralph « jusqu'à tout vert » sur l'existant** : son auteur ne l'y emploie pas (B§3).
- **Agent « plieur » imposé** : Cursor a supprimé son intégrateur, goulot (B§3 contradiction 2) ; à essayer sur une
  vague et mesurer, pas une règle.
- **Tests de mutation comme porte** : coûteux et bruyants sans boucle de retour (C§3).
- **Capture-recapture sur la suite des tours (152 → 78 → 30)** : population ouverte, axes différents : invalide (C§3).
- **Seuil « k < ~10 »** pour décider sur Chapman, **bad-fix 7 %** (Jones), **SUS 68**, **Mills** : de mémoire dans C —
  aucun ne devient règle (Mills seulement comme expérience).
- **Relecteur d'une autre famille par défaut** : dépendance payante, accord de Reda requis.
- **Phrase « tu es le propriétaire du code » pour les lanes EXISTANT** : +70-80 % de jetons, changements non demandés
  (A§3 [F52]).
- **Hooks `Stop` / `/goal`, `--max-turns`** (A§2 [BP]) : non lus en détail (A§8) et ils demanderaient de nouveaux
  réglages ; laissés pour un futur L5 sans témoin.
- **Raccourcir `CLAUDE.md`** (A§3) : hors de cette conception ; signalé § 5.
- **« Quality Wednesdays »** (C§2) : polissage récurrent après le merge, hors L4 ; les « peut attendre » au plan en
  tiennent lieu.
- **Baisser l'effort des relecteurs à `medium`** (A§7 [F52]) : aucune comparaison mesurée dans la maison (F§8) ;
  gardé opus/high, à essayer (§ 6).
- **Chiffres de promoteurs** (Every 95 %, Huntley 297 $, Devin 67 %, benchmark Greptile) : non repris (B§3).

## 5. Règles de `CLAUDE.md` à amender pour la cohérence (texte proposé, NON appliqué)
1. « **Go-deep levels** » — remplacer le paragraphe par : « « go deep » / « go very deep » / « go extremely deep » (ou
   « go L1 » … « go L3 ») map to calibrated investigation depths; « go L4 » / « go ship-grade » and « go L5 » / « go all
   the way » map to the ship-grade loop and the campaign — full doctrine in the **`go-deep` skill**, injected by the
   prompt hook. Every level first detects the regime (NEW / EXISTING / MIXED, read on `origin/main`) and announces it
   with the level. Without an explicit level, auto-pick L1-L3 per the skill and announce it in one line; the auto-pick
   NEVER chooses L4/L5 — it proposes them with their cost (Reda's named level always overrides). »
2. **WOW23 « TEST ECONOMICS »** — ajouter après « Local docker remains a debugging tool… » : « Exception: the go-deep
   L4/L5 review instrument (a private stack serving already-pushed code, mail in memory, no real key) has the status
   of rule 3-bis — an instrument for reviewers on the real screen, never a gate before a push. »
3. **MERGE FLOOR** — ajouter : « The ~100 cap counts PLAN TASKS; a go-deep L4/L5 round inscribes its corrections as
   plan tasks and merges as one wave the instant its CI is green. »
4. **3-bis** — ajouter : « go-deep reviewers are explorers: they tick nothing; any acceptance record they feed is
   replayed by the orchestrator (or a fresh agent) before it counts. »
5. **Model selection, Fable (a)** — ajouter : « the final adversarial critique of a go-deep L4/L5 run counts as that
   run's Fable pass ». Et, à « Fewest steps » : « a multi-round request (go-deep L4/L5) is bounded by its exit contract
   and the quota formula, not by enthusiasm ».
6. Hors de cette PR, à discuter avec Reda : A§3 recommande un `CLAUDE.md` court et des règles absolues en hooks ; la
   maison fait l'inverse (749 lignes mesurées par A). Rien n'est changé ici.

## 6. Ce qui reste incertain — un essai réel devra trancher
1. Les seuils de régime (P < 20 % / > 80 %) : sans source ; à calibrer sur les classements notés aux fichiers d'état.
2. « ≤ 25 points par tour » et la formule 90 / 65 : tirés d'un seul run, qui partageait le quota avec une autre session.
3. Le gain réel du test écrit par un autre (coût : un agent par tour ; gain attendu : moins de « partiel »).
4. Merge par tour : des régressions trouvées au tour suivant arrivent sur `main` entre deux tours (3 sur 191 au tour 1).
   Le deploy restant le geste de Reda, le risque paraît faible ; à confirmer.
5. Le coût de la critique du diff serveur à chaque merge (une opus par tour) contre ce qu'elle attrape.
6. Combien de lanes avec l'instrument monté (« moins de 8 » : 8 lanes saturaient déjà le CPU sans pile).
7. Relecteurs opus contre sonnet (jamais comparés, F§8) ; effort `medium` pour les consolidations.
8. L'outil d'usage de la session donne-t-il le % hebdomadaire ? (non essayé, F§7).
9. Faux positifs du crochet hors des 31 phrases essayées (« run l2 … », « go level 3 of »).
10. Chapman avec peu de constats communs ; le rappel par défauts semés ; le multiplicateur de coût de L5.
11. L'agent plieur (à essayer sur une vague).
12. Que la skill soit relue avec ses fichiers frères au bon moment (aucun autre skill de la maison n'en a ; le
    précédent observé est un plugin installé).

## 7. La PR sur `main` (branche `claude/go-deep-l4-l5`, docs / config seulement → CI rapide)
À toucher, exactement :
1. `.claude/skills/go-deep/SKILL.md` — remplacé par `projet/SKILL.md`.
2. `.claude/skills/go-deep/gabarits/{regime,contrat-de-sortie,registre,brief-relecteur,consolidation,brief-lane,instrument-de-revue,fiche-invariant,etat}.md` — nouveaux, copiés de `projet/gabarits/`.
3. `.claude/skills/go-deep/conception.md` — nouveau : ce fichier, § 3 et § 6 au moins (la skill le cite ; les chemins
   de la branche de notes y sont des références historiques, pas des liens à suivre).
4. `.claude/settings.json` — seule la valeur `hooks.UserPromptSubmit[0].hooks[0].command` (texte de `crochet.md`).
5. `CLAUDE.md` — seulement si Reda l'accepte (§ 5) ; sinon laisser intact et le dire au rapport.
6. `docs/claude-memory/go-deep-l4-l5.md` (nouveau : décisions, limites, coût mesuré) + une ligne dans
   `docs/claude-memory/MEMORY.md`.
À NE PAS toucher : rien sous `scripts/` (tout fichier `scripts/` met `backend=true` dans `ci.yml` et exige un
propriétaire) ; ni `docs/plans/**`, ni `docs/CODEMAP.md` (les empreintes ne couvrent ni skills ni mémoire, F§6), ni
`docs/audits/METHODE.md`, ni les skills `audit` (plafond de 80 lignes gardé), `qa-explorer`, `error-autopilot`. Le
script de l'instrument privé, le script de mesures DOM et un éventuel lecteur de registre sont des tâches `[ ]` futures
de leurs propriétaires.
