# Conception — go-deep L4 « ship-grade », L5 « all the way » et la sonde de régime (20/11/2026)

Ce fichier accompagne la skill : pour chaque choix, sa source et son STATUT. Il remplace `notes-de-conception.md` (R2).
Historique : R1 six lanes de recherche (`recherche/A…F`), R2 un concepteur, R3 trois vérificateurs neufs (`rejeu`,
`maison`, `faits`), tri de l'orchestrateur, R2-bis ce correcteur. Les chemins `recherche/`, `validation/`, `RETRO-METHODE.md`
sont ceux de la branche de notes `claude/erp-task-manager-ai-f8db1b` (`docs/taches/travail/r2/`) : des références
historiques, pas des liens à suivre depuis `main`.

Statuts : **mesuré** (une fois, au run du 19-20/11, rétro § n) · **lu** (source lue par une lane de recherche ou dans
cette session) · **maison** (règle écrite du dépôt : CLAUDE.md, METHODE, mémoire) · **départ** (choix de conception,
valeur de départ non calibrée : à recaler après le premier L4 lancé depuis la skill) · **vérifié** (rejoué dans
cette session).

## 1. Structure
| Choix | Source | Statut |
|---|---|---|
| `SKILL.md` court (L1-L3 mot pour mot de la skill du 24/08, régime court, résumés L4 / L5) ; `L4.md`, `L5.md`, `gabarits/` à côté, lus seulement pour L4 / L5 | tri D0 : la skill est chargée à chaque « go deep », un L1 ne paie pas L4 / L5 ; doc officielle Claude Code « Skills » : « Skills can include multiple files in their directory… access detailed reference material only when needed » et « Keep SKILL.md under 500 lines » | lu le 20/11 (code.claude.com/docs/en/skills) |
| Aucun précédent dans ce dépôt (7 skills, un `SKILL.md` chacune sur `origin/main`) ; précédent sur le poste : le plugin superpowers 5.1.0 | `git ls-tree origin/main .claude/skills` ; `maison.md` § 7 | vérifié |
| L4 / L5 = niveaux de `go-deep`, pas une deuxième skill ; gabarits COPIÉS dans le dossier de la skill (pas de renvoi vers la branche de notes) | F § 1, F § 6-7 | lu |

## 2. Chaque choix, sa source, son statut
| Choix | Source | Statut |
|---|---|---|
| Régime lu sur `origin/main`, annoncé avec le SHA ; worktree périmé 0 fichier contre 344 | D § 1.3 ; rejoué par `faits` | mesuré, vérifié |
| Règle de régime TOTALE ; tout l'arbre + synonymes ; outil / méthode classé sur l'artefact visé | `rejeu.md` § 3 (2 demandes réelles sur 4 mal classées) ; mesures de `regime.md` § 2 sur 81899193d | vérifié |
| Seuils 20 % / 80 % | D § 4.3 (proposition de la lane, sans source) | départ |
| Le choix automatique ne prend jamais L4 / L5 : il les propose | F § 1.9 ; METHODE §B.3 (annoncer le coût) | maison |
| Contrat de sortie chiffré au tour 0 ; une cible hors contrat ne bloque pas | A § 2 [HD] (contrat avant construction) ; B § 2 ; R § 6.5 | lu, mesuré |
| Seuils K (K2, K3, K6, K7, K8) | K3 : ≈ 85 % aux tours 2 et 3 (R § 3) ; les autres fixés par chaque run | départ |
| K4 ≤ 1/3 du rendement du tour 1, sur la même définition | proposition de C, sans source externe ; 25,3 → 15,6 → 7,5 retenus / relecteur, mais le 7,5 ne compte que les « avant le merge » (`faits` 13) | départ |
| Registre JSON Lines, ajout seulement, UN écrivain par fichier | A § 2 [HAR] (« less likely to inappropriately change or overwrite JSON files ») ; R § 6.8 ; `rejeu` B1 | lu, mesuré |
| Verdicts fermés de contre-vérification = ceux de `vérifie` | METHODE §C.4 | maison |
| Gravité S1-S4 (une seule échelle) | METHODE §B.2 ; `maison` I10 | maison |
| Relecteurs neufs, écran réel, preuve ; l'auteur ne valide jamais | R § 5.1-2 ; A § 1.1 ; E § 1 | mesuré, lu |
| 4-6 relecteurs par tour | R § 3 (6 / 5 / 4) | mesuré |
| Plancher = oracles 1-10 et règles 1-12 de qa-explorer, cités | `.claude/skills/qa-explorer/SKILL.md` STEP 2-3 | maison |
| Beauté par paires + mesures DOM, jamais une note absolue seule | E § 1.6, E § 2 (résumés) | lu |
| « Sec » = deux relecteurs différents ; accord 5-65 % | C § 1.2 : Hertzum & Jacobsen 2001, évaluateurs HUMAINS d'utilisabilité ; jamais mesuré pour des relecteurs LLM (E § 6) | lu (hors LLM) |
| Courbe lue par relecteur ; 152 → 78 → ~30 → 2 bloquants | R § 3 | mesuré |
| Classe → fiche d'invariant + liste greppée + MATRICE champ × condition ; cible du tour suivant | R § 6.1 ; `rejeu` § 2a et I1 | mesuré (classe revenue 4 fois) |
| Une garde par CLASSE, jamais par constat | METHODE §E anti-pattern 15 (70 gardes, +79 % en 7 j) | maison |
| Test premier écrit par un autre, sorties « contesté / impossible » | E § 2 (ImpossibleBench, voir § 4) ; A § 2 [HAR] | lu, avec réserves |
| Lane 0 seule, propriétaire du serveur ET de ses lecteurs ; PR brouillon au tour 0 lue job par job | R § 6.3 (400 → 409, 5 allers-retours) ; R § 4 (api-fuzz ne lisait pas le module) ; CLAUDE.md PACT10 | mesuré, maison |
| Table des identifiants partagés, greppée par la couture | R § 6.2 ; `rejeu` I3 | mesuré |
| Lanes : eslint + flake8 / py_compile + le test réparé ; capture « après » par la couture après la poussée | CLAUDE.md WOW23 ; mémoire `ci-avant-docker` ; `maison` I2-I3 | maison |
| Vagues de ~80 corrections, chacune mergée à sa CI verte | CLAUDE.md WOW23 / MERGE FLOOR ; R § 3 (102 corrections au tour 1) | maison, mesuré |
| Corrections au plan du propriétaire, AU FORMAT de ce plan | `maison` C2 ; METHODE §C.2, §C.4.5 ; `check_taches_cablage.py` bloquant | maison |
| Disjoncteur à 3 tentatives | B § 2 (Superpowers `fix-loop.md` : 5 tours) ramené à 3 | départ |
| Contre-vérification totale tant que non-fait + partiel > 10 %, puis S1-S2 + 25 % | 10 % : F § 3 C6 (proposition ; jamais atteint aux mesures, `faits` 11) ; 25 % : METHODE §C.4.2 | départ ; maison |
| Formule de quota k = min(3, ⌊(90 − u − 10) / c⌋), réserve finale 10, c = 25 puis mesuré | 74 points pour tour 0 + 3 tours + final, une part d'une autre session (R § 3) ; 74 / 3 ≈ 25 = borne haute ; F § 7 : aucune valeur écrite dans la maison | départ (seul point de données : R § 3) |
| Finale (vérification ciblée + critique du diff serveur) hors des tours, toujours jouée | R § 3 : elle a trouvé 2 bloquants et 7 corrections serveur ; `rejeu` B2 | mesuré |
| Fable : la critique finale seulement si ≥ ~40 tâches pliées ou surface à haut risque | CLAUDE.md « Model selection », cas (a) ; `faits` 5 | maison |
| Outil de quota `mcp__ccd_session_mgmt__get_usage` | essayé par `rejeu` et `maison` le 20/11 (« Weekly · all models 82 % ») | vérifié par eux, application de bureau seulement |
| Poste : 8 lanes + une boucle d'audit = 94-99 % CPU ; ≈ 1 Go par worktree ; 3 sous-agents par session pour un long run | mémoire du poste `machine_laptop_capacite` (10-11/11) | maison (mémoire) |
| QA de nuit 23:00 ; `TaqinorDevClean` 03:00 UTC, worktrees sans activité depuis 7 jours | tâches planifiées du poste et `C:\dev\clean-dev.ps1` (`StaleDays = 7`) | vérifié |
| Instrument : lanceur obligatoire + contrôle qui arrête le tour 0 | `maison` C3 (le lanceur du 19/11 passait le vrai `.env`, écoutait sur toutes les interfaces, partageait le réseau d'une pile à clés) | vérifié (construction de l'env et filtres du contrôle rejoués à sec ; Docker NON lancé) |
| L5 : WebKit pour l'iPhone | `rejeu` I10 ; `frontend/playwright.config.js` a un projet `mobile-safari` qui ne joue que `mobile.spec.js` ; `ms-playwright/webkit-2311` présent sur le poste | vérifié (contredit en partie `rejeu` : WebKit n'est pas « absent de la config ») |
| L5 : semaine simulée ; lecture prod après le deploy de Reda | `rejeu` I10 ; mémoire `prod-read-access` | départ ; maison |
| L5 : 30 min, 5 jours, 3 questions | C § 5 Q6 (inférence de la lane) | départ |
| L5 : pass^3 | A § 2 [EVAL] (0,75³ ≈ 0,42) ; k = 3 choisi | lu ; départ |
| L5 : Chapman, défauts semés, revalidation du harnais = expériences | C § 1.3 (formule) ; `rejeu` § 4 (sans effet en session unique) | lu ; départ |
| L5 : coût | aucun multiplicateur dérivable (`faits` 1) | non mesuré |
| Crochet | `maison` C1 ; table rejouée (`crochet.md`) : 72 phrases, 0 L4 / L5 à tort | vérifié |

## 3. Ce que les trois vérificateurs ont fait changer
- **rejeu** : registre à un fichier par écrivain (B1) ; plafond de coût qui n'efface plus la finale (B2) ; matrice des
  fiches d'invariant et classes données en cible (I1) ; PR brouillon et lecture des jobs au tour 0, Lane 0 propriétaire
  des lecteurs (I2) ; table des identifiants partagés (I3) ; outil de quota nommé (I4) ; sonde de régime totale, sur
  tout l'arbre et par synonymes (I5) ; événement `demande-croisee` et restes définis (I6) ; section du rédacteur de
  tests (I7) ; vérité sur les outils absents (I8) ; message de merge sur les corrections non contre-vérifiées (I9) ;
  WebKit, semaine simulée, lecture prod, et Chapman / revalidation rétrogradés (I10) ; repli de `plan_lanes.py` (I11) ;
  restes du module Tâches étiquetés « exemple ».
- **maison** : crochet (C1) ; format des tâches selon le plan (C2) ; instrument rendu sûr par un lanceur et un contrôle
  (C3) ; vagues (I1) ; contrôles des lanes et capture par la couture (I2-I3) ; statut de l'instrument rattaché à 3-bis
  et `ci-avant-docker`, sans se l'attribuer (I4) ; enregistrements d'acceptation (I5) ; claims `--owner` renouvelées
  (I6) ; décisions vers `decisions.yml` / `docs/claude-memory/` (I7) ; gestes de Reda en L5 (I8) ; L5 multi-sessions et
  Fable selon (a)(b)(c) (I9) ; S1-S4 (I10) ; poste mesuré au tour 0 (I11) ; quota illisible → tour 0 seul (I12).
- **faits** : coût de L5 « non mesuré » (1) ; 5-65 % situé (2) ; plafond de tours unique (3) ; valeurs de départ
  étiquetées (4) ; Fable conditionnel (5) ; chiffres de contre-vérification cités tels quels, écart 188 / 191 dit (6) ;
  `--owner`, « 8 lanes + une boucle d'audit », 44 px retiré, K4 comparable, réserves ImpossibleBench (optionnels).

## 4. Réserves sur les sources
- **ImpossibleBench** (E § 2) : tests cachés ≈ 0 triche MAIS ils dégradent le score sur le benchmark d'origine ; tests en
  lecture seule = « moyen terme », qui n'élimine pas le cas particulier codé en dur ; l'option d'abandon fait 54 → 9 %
  chez GPT-5 et 49 → 12 % chez o3, effet « much less pronounced » chez Opus 4.1, sans chiffre (`faits` 45). Le choix
  (test écrit par un autre, en lecture seule, + sortie « contesté / impossible ») reste peu coûteux ; son fondement
  chiffré vient de modèles OpenAI.
- **5-65 %** : évaluateurs humains, 2001, résumé seulement.
- **CodeRabbit 56,3 % de commentaires rejetés** (B § 3) : préimpression ; sert seulement à justifier qu'on mesure les écartés.

## 5. Écartés (et pourquoi)
- Notes sur 10 comme critère principal (E § 1.10) ; débat entre relecteurs, vote (E § 3) ; spec lourde pour l'existant
  et boucle « jusqu'à tout vert » (B § 3) ; agent « plieur » imposé (B § 3 : intégrateur supprimé chez Cursor) ; tests de
  mutation comme porte (C § 3) ; capture-recapture sur la suite des tours (population ouverte, C § 3) ; chiffres de
  promoteurs et de mémoire (Every, Huntley, Devin, SUS, bad-fix, Mills) ; autre famille de modèles par défaut (dépense) ;
  « tu es le propriétaire du code » dans les briefs (A § 3) ; hooks `Stop` / `/goal` (non lus en détail).
- Tri R3 : promouvoir tout de suite les scripts d'instrument dans `scripts/` (non testés hors Tâches) ; un gabarit de
  plus pour le rédacteur de tests (une section suffit).

## 6. Suites NON faites (à faire après un premier L4 réussi, chacune par sa propre PR)
1. Promouvoir les scripts d'instrument (lanceur, capture, semis, remise à zéro, mesures DOM, lecteur du registre) sous
   `scripts/` : tâches `[ ]` de leur propriétaire (tout fichier `scripts/` lance les jobs lourds et exige un propriétaire).
2. Calibrer les valeurs **départ** du § 2 sur le fichier d'état du premier L4 (c, réserve, 10 %, disjoncteur, seuils K,
   20 / 80 %), puis réécrire ce fichier.
3. Mesurer le coût réel de L5 sur sa première campagne.
4. Comparer relecteurs opus / sonnet et l'effort `medium` des consolidations (jamais comparés, F § 8).

## 7. Ce qui reste incertain
La finale tient-elle dans 10 points ; le coût de la critique du diff à chaque vague ; le gain du rédacteur de tests ;
le nombre d'agents à navigateur avec l'instrument monté ; faux positifs du crochet hors des 72 phrases jouées ; le
lanceur n'a pas été exécuté sous Docker dans cette session (seuls la construction de l'environnement et les filtres du
contrôle ont été rejoués à sec).

## 8. La PR à venir (branche `claude/go-deep-l4-l5`, docs / config seulement)
Fichiers, exactement :
1. `.claude/skills/go-deep/SKILL.md` — remplacé par `projet/SKILL.md`.
2. `.claude/skills/go-deep/L4.md`, `.claude/skills/go-deep/L5.md` — nouveaux.
3. `.claude/skills/go-deep/conception.md` — nouveau (ce fichier).
4. `.claude/skills/go-deep/gabarits/{regime,contrat-de-sortie,registre,brief-relecteur,consolidation,brief-lane,instrument-de-revue,fiche-invariant,etat}.md` — nouveaux.
5. `.claude/settings.json` — seule la valeur `hooks.UserPromptSubmit[0].hooks[0].command` (valeur JSON de `crochet.md`).
6. `docs/claude-memory/go-deep-l4-l5.md` (nouveau : ce que sont L4 / L5, quand, coût mesuré, limites) + une ligne dans
   `docs/claude-memory/MEMORY.md`.
7. `CLAUDE.md` — le seul paragraphe « Go-deep levels », remplacé par ce texte purement descriptif (aucune règle du
   fondateur ne change) :
   > **Go-deep levels.** « go deep » / « go very deep » / « go extremely deep » (or « go L1 » … « go L3 ») map to calibrated
   > investigation depths; « go L4 » / « go L5 » to the ship-grade loop and the multi-session campaign — full doctrine in the
   > **`go-deep` skill** (`.claude/skills/go-deep/`), injected by the prompt hook. Without an explicit level, auto-pick L1-L3 per
   > that skill and announce it in one line; L4 / L5 only when Reda names them (Reda's named level always overrides).
Rien sous `scripts/`, ni `docs/plans/**`, ni `docs/CODEMAP.md`, ni `docs/audits/METHODE.md`, ni les autres skills.
