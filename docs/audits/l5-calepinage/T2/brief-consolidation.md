# Brief de la consolidation — module Calepinage, tour 2 (go-deep L5)

« Before reporting progress, audit each claim against a tool result from this session. Only report work you can point
to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output. »

Tu es l'agent de CONSOLIDATION. Tu ne corriges aucun code. Tu lis ce que les relecteurs ont PROUVÉ sur l'écran réel,
tu vérifies chaque constat dans le code, tu nommes les classes de défaut, et tu inscris les corrections au plan du
propriétaire, dans le format de ce plan. Gabarit à suivre : `.claude/skills/go-deep/gabarits/consolidation.md` (ses
§ 0 à § 5 sont la forme de ta sortie) et `gabarits/registre.md` (formats et verdicts FERMÉS), `gabarits/fiche-invariant.md`
(une fiche par classe). Méthode des tâches : `docs/audits/METHODE.md` §C.2 (tâche v3, 14 clauses, `@model` obligatoire).

## Consolidation PAR LOTS (ajout du 23/11 — prime sur « Sorties » ci-dessous)

Le tour 2 a rendu plus de 330 verdicts et plus de 200 constats neufs : un seul agent n'y suffit pas. La consolidation
se fait en cinq LOTS indépendants, un agent par lot, puis l'orchestrateur assemble. Ton message de lancement te dit
ton lot. Tu ne lis QUE les fichiers de ton lot (registre et rapports) ; le code, lui, se lit partout.

| Lot | Périmètre | Relecteurs (fichiers `T2-<code>…`) | Ids de tâches réservés |
|---|---|---|---|
| A | Toit et gestes de dessin | F2-TOIT-a, F2-TOIT-b, F2-GESTES, F2-GESTES-b | ACAL1400 à ACAL1499 |
| B | Pose et électrique | F2-POSE-a, F2-POSE-b, F2-ELEC-a, F2-ELEC-b | ACAL1500 à ACAL1599 |
| C | Production : simulation, résultats, consommation | F2-SIMU-a, F2-SIMU-b, F2-RESU, F2-RESU-b, F2-CONSO, ORCH | ACAL1600 à ACAL1699 |
| D | Documents, parcours, liste | F2-DOCS-a, F2-DOCS-b, S2-PARCOURS, S2-PARCOURS-b, RATT-1, RATT-2, `T2/base-e2e.md`, « défauts voisins » des `registre/evenements/T2-lane-*.jsonl` | ACAL1700 à ACAL1799 |
| E | Écrans : maquettes v2, beauté, téléphone et tablette, fonctions manquantes | B2, T2, `T2/R1-beaute-simplicite.md`, `T2/R2-fonctions.md` § B, `maquettes-v2/` | ACAL1800 à ACAL1899 |

Sorties d'un lot (tu n'écris NI dans le plan NI dans `classes.jsonl` : l'orchestrateur assemble) :

1. `registre/evenements/T2-consolidation-<lot>.jsonl` — un événement par constat neuf de ton lot (forme du § Sorties 1).
2. `T2/consolidation/lot-<lot>-taches.md` — les tâches v3 de ton lot, écrites EXACTEMENT comme des lignes du plan
   (copie la forme des tâches ACAL1328 à ACAL1349 de `docs/plans/PLAN_AUDIT_CALEPINAGE.md` : `- [ ] **ACALn** …` avec
   ses clauses, `@lane`, `@model`, `Files:`, `@after`), rangées sous cinq titres exacts : `### M0 contrats`,
   `### M1 bloquant-fondateur`, `### M2`, `### GATED`, `### Acceptation en direct`. Ids pris dans TA plage, sans trou.
   - Une tâche de REPRISE par correction livrée au verdict `partiel`, `non-fait` ou `regression` (elle cite l'id
     d'origine et dit ce qui RESTE, d'après le champ `reste` du verdict et le rapport) — sauf quand plusieurs restes
     ont la MÊME cause dans le même symbole : alors UNE tâche qui les cite tous.
   - Une tâche par constat neuf retenu, ou par groupe de constats de même cause.
   - Un `partiel` dont le reste est seulement « cas non joué par le relecteur » (pas un défaut vu) n'est PAS une
     tâche de code : range-le dans `lot-<lot>.md` § « preuves à rejouer », pour le tour 3.
   - Gravité : M1 = S1-S2 (chiffre faux, donnée perdue, impasse, régression) ; M2 = S3 ; les S4 de style vont en
     une liste « optionnels » dans `lot-<lot>.md`, sans tâche.
   - Taille : une tâche = un défaut, corrigeable par une lane en moins d'une heure ; `Code net` borné.
3. `T2/classes/K-<NOM>.md` pour une classe NEUVE (≥ 2 constats de même racine dans ton lot ; vérifie d'abord qu'elle
   n'existe pas dans `T1/classes/`) ; pour une classe du tour 1 encore violée : `T2/classes/complement-<lot>.md`.
4. `T2/consolidation/lot-<lot>.md` — 60 lignes au plus : comptes (verdicts lus par valeur ; constats vus, retenus par
   gravité, doublons, écartés avec la raison), classes, choix de produit tranchés (avec le coût si faux), décisions
   ouvertes à écrire dans `docs/audits/decisions.yml` (tu les LISTES, tu n'écris pas le fichier), preuves à rejouer,
   optionnels, et la liste « tâche → fichiers » pour que l'orchestrateur vérifie la disjonction des lanes.

Les gardes du plan (dernier paragraphe des Règles) sont lancées par l'orchestrateur APRÈS l'assemblage. Toi, tu
vérifies avant de finir : chaque `Files:` existe (`ls`), chaque ancre `fichier::symbole` existe (`grep -n`), aucun id
hors de ta plage, aucun id en double.

## Entrées

- `docs/audits/l5-calepinage/registre/constats/T2-*.jsonl` (constats neufs) et
  `registre/evenements/T2-*-cv.jsonl` (verdicts de contre-vérification des corrections livrées) ;
- les rapports `docs/audits/l5-calepinage/T2/<code>.md` des relecteurs et leurs captures (chemins dans le registre) ;
- le contrat `docs/audits/l5-calepinage/contrat-de-sortie.md` ; les classes du tour 1 `T1/classes/K-*.md` ;
- le langage visuel et les maquettes v2 `docs/audits/l5-calepinage/maquettes-v2/` ;
- le code de la branche `claude/calpinage-module-l5-aadbde` (ton dossier courant) ; `docs/CODEMAP.md` §3-§4 d'abord.

## Sorties

1. `registre/evenements/T2-consolidation.jsonl` — UN événement par constat neuf (`retenu` · `doublon` ·
   `ecarte-artefact` · `ecarte-hors-perimetre` · `ecarte-faux` · `a-reproduire`) avec `cause` (`fichier::symbole`),
   `cause_statut` (`lue` · `probable` · `a-reproduire`), `correction`, `lane`, `tache`, `classe`.
2. Pour chaque correction livrée au verdict `partiel`, `non-fait` ou `regression` : une tâche de REPRISE (une par
   correction, qui cite l'id d'origine et ce qui reste), jamais la réouverture de l'ancienne ligne.
3. `registre/classes.jsonl` et une fiche `T2/classes/K-<nom>.md` par classe neuve (≥ 2 constats de même racine) ;
   les classes du tour 1 encore violées sont COMPLÉTÉES (endroits et matrice), pas dupliquées.
4. Les tâches au plan du propriétaire des fichiers (`python scripts/check_ownership.py --owner-of <fichiers>`) :
   `docs/plans/PLAN_AUDIT_CALEPINAGE.md` pour le calepinage — dans un NOUVEAU groupe en fin de plan, avant le
   `## DONE LOG` : `## Groupe ACAL — complément du 2026-11-23 (tour 2 du L5) · format v3`, sections « M0 contrats
   (seuls sur main d'abord) », « M1 bloquant-fondateur » (S1-S2), « M2 », « GATED », « Acceptation en direct » ; ids à
   la suite du plus grand id ACAL existant (`grep -o "ACAL[0-9]*" docs/plans/PLAN_AUDIT_*.md | sort -t L -k2 -n | tail -1`).
   Une tâche dont les fichiers ont plusieurs propriétaires → `docs/plans/PLAN_AUDIT_TRANSVERSE.md` avec
   `(@atomique: …)` ; une tâche d'un autre propriétaire → SON plan. Chaque tâche : les 14 clauses, calculées par
   `python scripts/audit_tache.py` (jamais affirmées), `@lane`, `@model`, `Files:`, `@after` quand elle dépend d'une
   autre. Les tâches d'écran citent la maquette v2 de leur écran et le LANGAGE v2.
5. `docs/audits/l5-calepinage/T2/consolidation.md` — 100 lignes au plus, au format du gabarit (§ 0 classes, § 1
   corrections par lane et par vague, § 2 écartés, § 3 choix de produit tranchés, § 4 lanes — sortie de
   `python scripts/plan_lanes.py docs/plans/PLAN_AUDIT_CALEPINAGE.md --workers 8 --wave-size 80` —, § 5 comptes).

## Règles

- Vocabulaire fixe : cause « lue » (ligne ouverte dans cette session), « probable », « à reproduire ». Jamais
  d'ancre `fichier:ligne`.
- Choix de produit : AUCUNE question au fondateur (consigne du 22/11 : « i want you to choose for me »). Tu tranches
  par la règle écrite — le plus simple pour l'utilisateur, sinon la maquette v2, sinon ce que font les références
  nommées — et tu écris chaque choix au § 3 avec son coût si faux ; jamais enregistré comme une décision de Reda.
  Un choix qui change un chiffre que voit un CLIENT (PDF, page publique) ne se tranche pas : tâche GATED, décision
  ouverte dans `docs/audits/decisions.yml` (id suivant `D-ACAL-<n>`), dite au § 3.
- Hors périmètre du L5 (à signaler, sans tâche de correction ici) : le PDF client `/proposal`, les statuts de devis,
  le moteur de devis et l'argent ; le rapprochement « un seul moteur, celui du CRM » et le lead 1742 — phase de
  contrôles. Un constat qui en relève : `ecarte-hors-perimetre` avec la raison, et une ligne dans le § 2.
- Calibrage : correction de justesse ou de spec seulement ; style et durcissement hypothétique → S4, optionnels.
  Tout chiffre faux ou inventé est une correction de justesse, jamais optionnelle.
- Avant de finir, les gardes : `python scripts/check_taches_cablage.py`, `python scripts/check_ancres_taches.py`,
  `python scripts/check_ownership.py`, `python scripts/check_decisions.py`, `python scripts/audit_registre.py --check`
  et `python scripts/plan_lanes.py docs/plans/PLAN_AUDIT_CALEPINAGE.md` (0 refus neuf) — toutes vertes, sorties
  collées dans `consolidation.md` § 5. Aucun `git add`, aucun commit : l'orchestrateur relit et commite.

Ton message final : 15 lignes au plus — comptes (vus, retenus par gravité, doublons, écartés), contre-vérification
(ok / partiel / non-fait / faux / régression / déjà-présent), classes, tâches écrites (ids), lanes et vagues, gardes.
