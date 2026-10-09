---
name: audit-methode-v3
description: Audit L3 de la méthode d'audit (09/10/2026, PR #907) — faits mesurés, décisions fondateur, où tout vit (METHODE v3, skill, dossier AMET, sondes, decisions.yml, 59 tâches v3), ce qui reste à construire et dans quel ordre
metadata:
  type: project
---

# Audit de la méthode d'audit — 09/10/2026 (groupe AMET, PR #907)

**Demande de Reda** : « go extremely deep » sur le script d'audit pour que (1) chaque tâche corrige son problème en un
coup, (2) l'ERP soit « des parcours qui tournent seuls et que l'utilisateur modifie à chaque étape », (3) le code ne
soit pas répété, (4) les travers d'un ERP écrit par un non-codeur via LLM soient détectés et corrigés, (5) le découpage
en unités soit ré-examiné. Session L3 : 9 lanes R1 → 6 conceptions R2 → 7 vérificateurs frais R3 (10 sondes exécutées
sur la pile locale en transaction annulée) → 1 critique Fable R4.

## Où tout vit (lisible depuis n'importe quel poste après `git pull`)
- Dossier complet (premier dossier au format v3) : `docs/audits/2026-10-09-methode.md` — 25 constats C-AMET-001…029,
  couverture, réfutations, non-risques, décisions, coût (≈ 9,6 M jetons de sous-agents).
- Méthode : `docs/audits/METHODE.md` v3 (363 l.), skill `.claude/skills/audit/SKILL.md` v3, gabarit `docs/audits/GABARIT_DOSSIER.md`,
  décisions `docs/audits/decisions.yml`, registre `docs/audits/unites.yml` (champ `dossier:`), sondes `docs/audits/sondes/AMET/`.
- Garde basculée : `scripts/check_taches_cablage.py` FORME 5 bi-format (`CLAUSES_AUDIT_V3`, 14 libellés ; `n/a` nu et
  absence de `@model` refusés) ; tâches v2 gelées dans `scripts/taches_audit_v2.txt` (ne fait que rétrécir).
- CLAUDE.md : étape 3-bis (acceptation live par l'orchestrateur), règles des tâches d'audit (clauses calculées, test dans
  le module existant, code net, @after inter-lanes, décisions), rapport de merge, `@model` obligatoire en v3.
- 59 tâches v3 (`grep "gen manuel" docs/plans/PLAN_AUDIT_*.md`) : 12 écarts `vérifie` sur défauts VÉRIFIÉS PAR SONDE
  (ATOT35-38, AFAC100-101, ACAL352, ASTK240-243, ACHT100), groupe AMET : 18 M0, 26 M2, 2 M3, 1 acceptation (AMET102) ;
  outillage dans `docs/plans/PLAN_AUDIT_DEPLOY.md` (AMET80-AMET101).

## Faits mesurés (à ne pas re-dériver)
- 48 % des 48 tâches cochées re-vérifiées étaient corrigées en un coup (79 % justes sur main) ; 2 régressions d'écran
  sous CI verte (ATOT2 : « Facturer » réaffiché après facture complète ; ATOT9 : toute sauvegarde d'une facture émise
  depuis le formulaire = 400).
- 0/19 acceptations live jouées, 0 `vérifie`, registre jamais avancé (les tâches d'acceptation étaient confiées à des
  lanes sans pile ; un groupe est mergé 1-18 fois, médiane 4).
- Clauses affirmées, jamais calculées : Appelants / Jumeaux / Listes figées faux dans ≈ 20/48 ; 75 réparations CI
  « test périmé » ; 53 % des ancres `fichier:ligne` dérivées ; 4 565 `n/a` sur 1 609 tâches.
- Code : +17 % en 7 jours ; 65 fichiers ≥ 2 000 l. ; 97 groupes de fonctions identiques ; 523 façades F401 ; 39 % des
  5 401 fichiers de test nommés par une tâche ; 70 gardes, 4 176 entrées de baseline (+79 %).
- Découpage : 32 % des tâches hors unité ; TRANSVERSE = lane de 285 tâches (82 multi-propriétaires = {crm, lead}).
- Parcours : 27/81 étapes automatiques ; 13 portes de création de lead ; 8 écrasements de saisie manuelle ; conditions
  de paiement lues EN DIRECT sur les devis signés (sonde : 60 %/38 280 → 40 %/25 520 après un PATCH Paramètres).
- Coût des 19 audits v2 : ≈ 85 M jetons (D3 calepinage 37 M = anti-exemple) ; recette v3 : L3 4,7-6,7 M, plafond 8 M.

## Décisions fondateur (docs/audits/decisions.yml — ne jamais re-demander)
D-ECH-FIGE (a) échéancier figé sur le devis à l'acceptation, devis signés tamponnés après dry-run · D-ATOT5 (a) un avoir
réduit le dû, type d'avoir (correction / geste commercial / retour) · D-SIGN-AUTO (a) facture d'acompte créée en
BROUILLON à la signature, BC manuel · D-OWN-FUSION (a) fusion crm → lead et générateur → devis, déplacement verbatim
des tâches TRANSVERSE, scissions, correctifs d'abord (porteur : AMET101) · D-FORMAT-V3 (a) · D-SCOPE-0910 (a) méthode +
garde + tâches dans la session, scripts par plan-run · D-CLAUDEMD (a) Claude édite CLAUDE.md · D-PROVENANCE (a) survivant
= motif `Devis.overrides` généralisé dans `apps/records/provenance.py` (`ecrire_si_libre`, champ `saisies_humaines`) ·
D-SPL-ATOMIQUE (a) SPL atomiques en TRANSVERSE avec `(@atomique: …)`.

## Suite, dans l'ordre
1. `work on the plan audit_deploy` — outillage AMET (générateur de clauses AMET80-82, gardes AMET83-85, CI AMET86,
   acceptation AMET88-90, registre AMET91, lint AMET92, sondes AMET93, décisions AMET94, planner AMET95-97, parcours AMET98,
   pile AMET99, clés par symbole AMET100).
2. `work on the plan audit_facturation` / `audit_devis` — D-ECH-FIGE, D-ATOT5, D-SIGN-AUTO, boutons Facturer, portes BC.
3. AMET101 — migration de propriété (PR dédiée, casse l'append-only une fois ; restaurer 21 chemins + 34 prédécesseurs
   de la simulation R2_4 avant d'appliquer).
4. `vérifie ASTK` = premier run v3 ; puis `audit parcours PA4` (argent) comme premier audit par parcours.

## Leçons de run (CLAUDE.md « Fleet quality »)
- Les clauses d'une tâche se CALCULENT (grep / AST), elles ne s'affirment pas : la critique Fable a trouvé dans mes
  propres lignes un mauvais fichier pour `next_tranche`, un nombre inventé et 6 classes de test inexistantes — la garde
  v3 et le balayage mécanique des ancres sont là pour ça.
- Sur un poste à 16 Go avec Docker, une flotte de 6 agents opus + vérificateurs fait redémarrer l'app Electron (les
  agents de fond meurent avec elle, sans trace) : ≤ 2-3 agents de fond, écriture incrémentale sur disque, commit après
  chaque fichier. Le conteneur local envoie de VRAIS mails (clé SendGrid dans `.env`) : toute sonde force un backend
  mail en mémoire.

**Why:** Reda (09/10/2026) veut pouvoir reprendre cet audit depuis n'importe quel poste avec tous ses détails.

**How to apply:** tout audit, `vérifie` et plan-run d'un groupe d'audit suit METHODE v3 ; lire le dossier avant de
lancer l'outillage AMET ; ne jamais re-poser les décisions ci-dessus. Voir [[audits-modules]], [[propriete-fichiers]],
[[lecons-construction-qjr5]].
