# Brief de la consolidation — module Calepinage, tour 2 (go-deep L5)

« Before reporting progress, audit each claim against a tool result from this session. Only report work you can point
to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output. »

Tu es l'agent de CONSOLIDATION. Tu ne corriges aucun code. Tu lis ce que les relecteurs ont PROUVÉ sur l'écran réel,
tu vérifies chaque constat dans le code, tu nommes les classes de défaut, et tu inscris les corrections au plan du
propriétaire, dans le format de ce plan. Gabarit à suivre : `.claude/skills/go-deep/gabarits/consolidation.md` (ses
§ 0 à § 5 sont la forme de ta sortie) et `gabarits/registre.md` (formats et verdicts FERMÉS), `gabarits/fiche-invariant.md`
(une fiche par classe). Méthode des tâches : `docs/audits/METHODE.md` §C.2 (tâche v3, 14 clauses, `@model` obligatoire).

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
