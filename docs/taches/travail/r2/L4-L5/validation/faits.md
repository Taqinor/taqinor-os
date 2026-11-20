# Validation R3 — lentille « faits » (zéro fait inventé) — projet go-deep L4/L5

Vérificateur neuf, lecture seule. Preuves : commandes sur `origin/main` (81899193d) et sur 6623b6ea3, rejeu du crochet
(Git Bash, 40 phrases), rejeu du script de courbe, `gh pr view 1447`, 8 appels web (MA, HAR, HD, ImpossibleBench x2,
arXiv 2607.03316, Superpowers `fix-loop.md`, recherche Hertzum). Codes : F fondé · A affaibli · D déformé · S sans source ·
I inférence présentée comme un fait · C choix de conception (ok seulement s'il est dit tel).
Sigles de source : A-F = rapports `recherche/`, R§n = `RETRO-METHODE.md`, N§n = `notes-de-conception.md`.

## 1. Tableau des affirmations (regroupées ; un `#` = une affirmation vérifiée)

| # | Fichier — affirmation | Source et statut (rapport / vérifié ici) | V |
|---|---|---|---|
| 1 | SKILL — multi-agent « up to ~15× a chat » | A [MA] lu ; page rouverte : « about 15× more tokens than chats » | F |
| 2 | SKILL — « a first PR of 324 files » | D §4.6 ; `gh pr view 1447` : 324 fichiers, +42 132 | F |
| 3 | SKILL/regime — worktree périmé : 0 fichier contre 344 sur `main` | D §1.3 ; rejoué : worktree 0 fichier + `check_ownership --owner-of` « AUCUN » ; `origin/main` 203 back + 141 front = 344 | F |
| 4 | SKILL — « copilote » : 11 mentions CODEMAP, 0 fichier | D §4.2 ; rejoué : F=0, MAP=11 | F |
| 5 | SKILL — « 3 then 2 regressions » | R§3 (3 sur 191 ; 2 au tour 2) | F |
| 6 | SKILL — « ≈ 25 % of « proven » fixes half-done » | R§4 ; R§3 donne 37 « à moitié » + 5 « pas réglées » + 3 régressions sur 191 = 19 % à moitié, 22 % sans les régressions, 24 % avec ; 143+37+5+3 = 188 ≠ 191 | A |
| 7 | SKILL — « 152 findings → this loop took it to 2 blockers » | R§3 : 152 (tous constats) → 78 → ~30 (« avant le merge » seulement) → 2 bloquants d'un autre type de contrôle (vérif. ciblée + critique serveur) | A |
| 8 | SKILL — mesuré : 16 relecteurs, ≈ 40 agents de correction, 3 consolidations | R§3 | F |
| 9 | SKILL — « ≈ 74 points (6 → 80 %) for 3 rounds + final » → « ≤ 25 / round » | R§3 (74 dont une part d'une autre session) ; 74/3 = 24,7 : borne haute, dite « (some from another session) » | F |
| 10 | SKILL — L5 « ≈ +25 % reviewers … ≈ 1,3-1,5 × L4 » | C §2 « +2 relecteurs par tour ≈ +25 % sur 16 » ; la skill dit « 2 reviewers … per round » = +6 à +8 sur 16 = +38 à +50 % ; relecteurs ≈ 6,4 M sur 26-38 M (R§6.7) ⇒ +25 % relecteurs ≈ +4-6 % du total ; aucun calcul ne donne 1,3-1,5 | S |
| 11 | SKILL — « evaluator agreement runs 5-65 % » (règle du « sec ») | C §1.2 lu-recherche ; rouvert : Hertzum & Jacobsen 2001, 11 études, évaluateurs HUMAINS (cognitive walkthrough, heuristique, think-aloud), résumé seulement ; E §6 : aucune mesure sur deux relecteurs LLM | A |
| 12 | SKILL — Chapman N = (n+1)(K+1)/(k+1) − 1, « borne basse, instable » | C §1.3 (Wikipédia), formule standard exacte ; aucun seuil k n'est repris | F |
| 13 | SKILL — « pass^3 » critique | A [EVAL] : 0,75³ = 0,42 ; k = 3 choix (C) | F |
| 14 | SKILL — « ~20 cases Reda scored once » (juges de beauté) | A/E : « ≈ 20 requêtes » (page MA relue) sert à DÉMARRER un jeu d'évals ; E y accroche « Reda note ~20 cas » = adaptation de l'auteur | I |
| 15 | SKILL — « 30 min on a real device, 5 days of real use, 3 debrief questions » | C §5 Q6 : « inférence de la lane » ; absent de la skill | S |
| 16 | SKILL — breaker : 3 tentatives (2 lane, 1 neuf d'un cran au-dessus) | Superpowers `fix-loop.md` relu : 5 tours (1-3 même, 4-5 neuf plus fort) ; 3 = « mon choix » (N§3), non dit dans SKILL | C |
| 17 | SKILL — k = floor((90 − u − 5)/25), « pas de tour à u ≥ 65 », arrêt à 90 %, « 10 points pour Reda, 5 pour le final » | F §7 : « aucune valeur écrite » ; N§6.2 les dit non calibrés, SKILL ne le dit pas ; 65 incohérent avec la formule (k = 0 dès u > 60) | C |
| 18 | SKILL — « non-fait + partiel ≤ 10 % puis A + 25 % » | 10 % = F §3 C6 (proposition) ; 25 % = METHODE §C.4.2 (« toutes P0/S1 + 25 %, min 8, max 48 ») ; données 24 % → 15 % → 15 % (4/27) : le seuil 10 % n'a jamais été atteint | C |
| 19 | SKILL — signaux/seuils de régime 20 % / 80 %, ≥ 2 signaux forts absents | D §4.3 « sans source » ; SKILL écrit « Uncalibrated thresholds » | F |
| 20 | SKILL — « 8 lanes used 94-99 % [CPU] without a stack », 4 cœurs / 34 Go, ≈ 1 Go / worktree, Docker relance une pile avec clé d'envoi réelle | mémoire `machine_laptop_capacite` : « 8 lanes + une boucle d'audit » (rien sur la pile) ; 4/34 Go, 1 Go, Docker : conformes | A |
| 21 | SKILL — « a late 400 → 409 cost 5 CI round-trips » | R§6.3 | F |
| 22 | SKILL — Fable : L4 « 1 — the final critique » ; « Tensions … none overrides » | CLAUDE.md l. 391-404 : « A small batch (<~40 routine tasks, no high-risk surface) does NOT get a Fable pass » ; L4 l'accorde sans condition | D |
| 23 | SKILL/contrat — plafond : « 3 rounds + final » (SKILL) contre « k (≤ 3) + le dernier tour « avant le merge » » (contrat § 2) | R§3 : 3 tours dont le 3e = « avant le merge », puis « final » = 1 relecteur + 1 critique ; le contrat permet 4 tours de relecteurs × ≤ 25 pts | D |
| 24 | SKILL — renvois : METHODE §B.3 (8 M), §B.6, §C.4 (verdicts fermés), §C.4.7, §A.2, §E anti-patterns 1/11/15 ; WOW23, MERGE FLOOR, 3-bis, PACT10, D-CLAIMS-MERGE | `git show origin/main:…` : tous présents, sous ce nom | F |
| 25 | SKILL/brief — qa-explorer STEP 2 oracles 1-10, STEP 3 règles 1-12 | `origin/main` : 10 oracles, 12 règles ; (l'oracle 10 est joué par l'orchestrateur sans navigateur, pas par un relecteur) | F |
| 26 | SKILL/contrat — `plan_claims.py claim file:<plan> app:<m>` | le script exige `--owner <id>` (argparse `required=True`) ; l'exemple de la skill échouerait | D |
| 27 | SKILL — `plan_lanes.py`, tags `@lane @files @model @after`, `plan_lanes.py` sans option | tags et options présents (`--workers`, `--wave-size`, `--check`, `--sans-pile`) | F |
| 28 | SKILL — Fable « 2× opus per token » ; `CLAUDE_CODE_SUBAGENT_MODEL` UNSET ; jamais de `/model` en cours | CLAUDE.md (« $10/$50 — 2× Opus ») | F |
| 29 | SKILL — « 239 lignes » (N en-tête) ; `check_audit_dossier.py` plafond 80 | `wc -l` : 239 ; `PLAFOND_SKILL = 80` | F |
| 30 | crochet — 31 phrases + 7 à retour de ligne, résultats du tableau | rejoué : 40 phrases dont les 38 du tableau, tous résultats identiques ; JSON de `settings` = commande (égalité exacte) ; « go L3-L4 » aucun ; faux positifs « run l2 cache », « go level 3 of » confirmés | F |
| 31 | crochet — colonne « actuel » (L1 pour « go deeper », aucun pour « go L3 ») | regex de `origin/main:.claude/settings.json` : `go +deep` matche « go deeper » ; pas de forme « go L3 » | F |
| 32 | crochet — « 0,3 à 0,7 s par appel », « jq absent » | non rejoué (secondaire) | A |
| 33 | regime — table du 20/11 sur 6623b6ea3 (taches 344/92/10/200-0/1/5/1/0/6 ; calepinage 1 070/606/4/3/63/2 ; cpq PARQ 1, 0 `urls.py`) | rejoué commande par commande : identique. (D donnait 82 tests, 49, 119 front : périmés, le projet a re-mesuré à raison) | F |
| 34 | regime — verbes d'existant/neuf = indices ; 5 cas où la règle se trompe | D §4.7, Fowler/Spolsky par résumé ; présenté comme parade, pas comme mesure | F |
| 35 | contrat — K4 « ≤ 1/3 du tour 1 (proposition, sans source externe) » ; K8 « aucune source n'en donne » | dits tels dans le gabarit ; 7,5/25,3 = 0,30 (le « ~30 » du tour 3 ne compte que « avant le merge ») | F |
| 36 | contrat — K3 « ≥ 85-90 % ok » | R§3 : ≈ 85 % aux tours 2 et 3 ; valeur de départ non étiquetée | C |
| 37 | contrat — K7 « cibles ≥ 44 px » | seule trace : F §4 (proposition) ; norme courante (Apple HIG, WCAG 2.5.5) mais aucune source dans les rapports | S |
| 38 | registre — « un modèle écrase moins volontiers un JSON qu'un Markdown » | HAR rouvert : « less likely to inappropriately change or overwrite JSON files compared to Markdown » ; seul `passes` modifiable ; « > 200 features » | F |
| 39 | registre — script de courbe | exécuté sur l'exemple : sort le tableau annoncé. (« écartés % » compte les `doublon` comme du bruit : voir constat 12) | F |
| 40 | registre/brief — courbe par relecteur 25,3 → 15,6 → 7,5 ; « 152 → 78 → 30 cachait 6, 5, 4 » | R§3 : 152/6, 78/5, 30/4 exacts ; ratios 0,51 / 0,38 exacts | F |
| 41 | brief-lane — garde ADEP24 (`waitForTimeout`, `setTimeout`) ; axe 4.14 contre 4.12 ; imports sur une ligne, etc. | `check_test_determinism.py` + `ci_guards.py` présents ; axe : R§4 | F |
| 42 | instrument — « 100 connexions », `DB_CONN_MAX_AGE=0`, METHODE §A.2 mail en mémoire | mémoire `local_ci_via_docker` l. 96-98 ; METHODE §A.2 relu | F |
| 43 | fiche-invariant — « même classe QUATRE fois » ; anti-pattern 15 « 70 gardes, +79 % en 7 j » | R§6.1 ; METHODE §E ligne 15 | F |
| 44 | notes §3 — « CodeRabbit : 56,3 % rejetés, préimpression » | arXiv 2607.03316 rouvert : 36,4 / 7,3 / 56,3 %, 31 073 paires, 10 191 PR, 239 dépôts, préimpression (3/7/2026) | F |
| 45 | notes §3 — « ImpossibleBench : tests cachés ≈ 0 triche ; option d'abandon 54 % → 9 % chez GPT-5 » (justifie test en lecture seule + sortie « impossible ») | corps rouvert : cachés « near zero » MAIS « degrades performance on the original benchmark » ; lecture seule = « middle ground », n'élimine pas le special-casing, « particularly effective against Opus-4.1 » ; 54→9 % GPT-5, 49→12 % o3 ; pour Opus 4.1 « much less pronounced » (aucun chiffre) | D |
| 46 | notes §3 — Superpowers « 5 tours, 4-5 par un frais plus fort » | `fix-loop.md` rouvert : exact | F |
| 47 | notes §3 / SKILL — HD : évaluateur séparé plus facile à rendre sceptique ; 27 critères ; 20 min 9 $ contre 6 h 200 $ ; évaluateur « overhead » avec Opus 4.6 | HD rouvert : exact (« far more tractable », « Sprint 3 alone had 27 criteria », « over 20x », « unnecessary overhead » sous le seuil solo) ; la skill ne reprend pas la réserve « inutile si la tâche est à portée solo » (N§6.7 la laisse ouverte) | F |
| 48 | notes §3 — MA : 80 % de la variance (jetons), 1 agent / 3-10 appels, 2-4 / 10-15, > 10 ; « ≈ 20 requêtes » ; juge à un appel 0,0-1,0 | MA rouvert : exact | F |
| 49 | notes §1/§6 — « 749 lignes » de CLAUDE.md (A) | `origin/main` : 755 | A |
| 50 | notes §7 — « scripts/ met backend=true ; `.claude/**`, `docs/**` ne lancent que stage-names » | `ci.yml` l. 289, 353 : exact | F |
| 51 | notes §4 — écartés : Every 95 %, Huntley 297 $, Devin 67 %, Deque 57 %, SUS 68, bad-fix 7 %, Mills | B §3, C §6 : marqués promoteur / mémoire ; aucun n'entre dans SKILL ni gabarits | F |

Rapports de recherche (sondage demandé, 8 appels web) :
| R | Affirmation « lue » | Page | V |
|---|---|---|---|
| R1 | A : 15× chat, 80 % de variance ; « tâches de code mal adaptées » | MA : 15× et 80 % exacts ; la page dit « fewer truly parallelizable tasks than research », A durcit en « mauvais choix pour la plupart » | F (nuance) |
| R2 | A : JSON, seul `passes` modifiable, « retirer/éditer un test inacceptable » | HAR : exact | F |
| R3 | A : contrat de sprint 27 critères, 20×, évaluateur surcoût | HD : exact | F |
| R4 | E : ImpossibleBench 54→9 %, tests cachés ≈ 0 ; stricte >85 → 1 % | corps : exact ; « tests en lecture seule = moyen terme » et la dégradation du benchmark sont dits | F |
| R5 | B : CodeRabbit 36,4/7,3/56,3 % | arXiv : exact | F |
| R6 | C : accord 5-65 % entre deux évaluateurs (lu-recherche) | exact mais évaluateurs humains, 2001, résumé | F (hors-sujet LLM) |
| R7 | A §1.2 : « Anthropic confirme notre chiffre ≈ 25 % » | HD ne donne aucun taux ; il dit seulement que les agents « skew positive » | D (non repris par le projet) |

Totaux (lignes 1-51 + R1-R7 = 58) : F 39 · A 6 (6, 7, 11, 20, 32, 49) · D 5 (22, 23, 26, 45, R7) · S 3 (10, 15, 37) · I 1 (14) ·
C 4 (16, 17, 18, 36 : choix de conception sans mesure ; constat seulement si la skill ne les dit pas, voir § 2 constat 4).
Le tableau regroupe parfois plusieurs chiffres par ligne : ≈ 150 chiffres, noms ou renvois individuels contrôlés.

## 2. Constats (aucun bloquant : aucune règle de la skill ne repose sur un fait faux ; 6 importants, 8 optionnels)

**Bloquants : 0.** Les chiffres rapportés au dépôt, au crochet et aux sources web rouvertes sont justes. Les fautes sont de
transposition, de cadrage et de chiffres non dérivés.

### Importants
1. **Multiplicateur de coût de L5 sans dérivation (ligne 10).** SKILL « Cost: ≈ +25 % reviewers … ≈ 1,3-1,5 × L4 ». Le +25 % vient
   de C (« +2 par tour ≈ +25 % sur 16 ») alors que la skill met 2 relecteurs PAR TOUR (+38 à +50 %), et les relecteurs ne pèsent
   que ≈ 20 % des jetons (16 × 0,4 M contre 40 × 0,5-0,8 M, R§6.7). Correction : « Coût L5 : non mesuré. Surcoûts connus : +2
   relecteurs par tour, une lane de figeage, 30 min + 5 jours de Reda ; aucun multiplicateur n'est dérivé — l'annoncer « à
   mesurer au premier run L5 ». » Retirer « 1,3-1,5 × » du tableau et « Typical agents » (ou le marquer « conjecture »).
2. **« Evaluator agreement runs 5-65 % » (11).** Donnée sur des évaluateurs humains de facilité d'usage (2001, résumé), pas sur des
   relecteurs LLM ; E §6 dit n'avoir trouvé aucune mesure LLM. Correction : « (évaluateurs humains, Hertzum & Jacobsen 2001 :
   5-65 % ; jamais mesuré pour nos relecteurs — d'où deux relecteurs différents) ».
3. **Plafond de tours contradictoire (23).** SKILL « 3 rounds + final » ; contrat § 2 « k (≤ 3) + le dernier tour ». Au run mesuré,
   le dernier tour « avant le merge » ÉTAIT le tour 3. Correction du contrat : « Tours : k (≤ 3, le dernier = « avant le merge »)
   + la vérification finale ».
4. **Paramètres de conception présentés sans étiquette (17, 18, 15, 16, 36).** k = floor((90−u−5)/25), 65 %/90 %, 10 %/25 %,
   3 tentatives, 30 min/5 jours, K3 85-90 %. N§6 les dit non calibrés ; SKILL non (hors régime). Correction : une phrase en tête
   des Guardrails : « Toutes les valeurs numériques ci-dessous sont des valeurs de départ tirées d'UN run (19-20/11), non
   calibrées ; recalibrer après le premier run L4 (conception.md § 6). » Et harmoniser 65 % (« pas de tour à u ≥ 65 ») avec la
   formule (k = 0 dès u > 60) : mettre 60, ou dire que 65 laisse la marge du final.
5. **Fable L4 inconditionnel (22).** Contraire à CLAUDE.md (« petit lot : pas de Fable »). N§5.5 propose l'amendement mais la skill se
   dit sans conflit (« none overrides »). Correction : « 1 — la critique finale si le lot dépasse ≈ 40 tâches ou touche règle
   #4 / auth / architecture, sinon Opus ».
6. **« ≈ 25 % half-done » (6).** Phrase chiffrée à la place la plus lue. Réel : 37/191 = 19 % à moitié ; 45/191 = 24 % « pas pleinement réglées »
   (avec 5 non-faits et 3 régressions) ; 143+37+5+3 = 188 ≠ 191 et 191 ≠ 102 corrections du tour 1 (dénominateur non réconcilié
   dans R§3). Correction : « ≈ 20-25 % of « proven » fixes not fully settled at round 1 (37 half, 5 not, 3 regressions of 191) ».

### Optionnels
7. `plan_claims.py claim …` sans `--owner <hôte>/<branche>` (26) : l'ajouter à l'exemple de SKILL (tour 0).
8. Notes §3 / conception.md : compléter la ligne ImpossibleBench (45) : cachés dégradent le benchmark, lecture seule = « moyen terme »,
   effet de la sortie « impossible » « much less pronounced » sur Opus 4.1 (nos agents sont des Claude). Le choix (test en lecture
   seule + sortie « contesté ») reste bon marché, mais son fondement est celui d'un modèle OpenAI.
9. SKILL « 8 lanes used 94-99 % without a stack » (20) : la mémoire dit « 8 lanes + une boucle d'audit » ; retirer « without a stack ».
10. K7 « cibles ≥ 44 px » (37) : marquer « exemple (Apple HIG / WCAG 2.5.5) » ou laisser `<n>`.
11. Seuil 10 % de contre-vérification : jamais atteint par les mesures (24 → 15 → 15 %) ; N§1 ligne 7 compte un gain « réduit » qui ne
    s'est pas produit. Écrire « gain attendu, non observé ».
12. Registre § 5 : « écartés % » = 1 − retenus/vus compte les `doublon` et `a-reproduire` comme du bruit ; séparer `ecarte-*` des `doublon`
    pour que « un axe qui produit du bruit » ne soit pas un axe qui double les autres.
13. K4 : le « ~30 » du tour 3 est un sous-ensemble (« avant le merge ») comparé au 152 complet ; dire qu'en L4 la mesure est « retenus
    / relecteur / tour » sur la même définition.
14. Notes : « 749 lignes » de CLAUDE.md → 755 aujourd'hui ; renvoi `conception.md` et `gabarits/` de la skill : n'existent qu'une fois la PR
    faite (N§7 les prévoit, vérifier au merge) ; `plan_drain_ci_bug_classes` et `machine_laptop_capacite` sont des mémoires de
    l'utilisateur, pas du dépôt ; le crochet (durée, `jq`) non rejoué.

## 3. Ce qui tient
Renvois internes tous résolus ; régime et crochet reproduits à l'identique ; sources web essentielles (MA, HAR, HD, CodeRabbit,
Superpowers, ImpossibleBench) fidèlement rapportées, avec leurs statuts de lecture honnêtes dans les rapports ; l'étiquetage
« non calibré / sans source » est correct dans `regime.md`, `contrat-de-sortie.md` (K4, K8) et `notes-de-conception.md` §6.
