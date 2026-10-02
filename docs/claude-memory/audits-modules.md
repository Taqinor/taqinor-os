---
name: audits-modules
description: Pointeur — les audits par module v1 (« audit <module> », « vérifie <groupe> ») sont remplacés depuis le 02/10/2026 par le skill audit + docs/audits/{METHODE.md,unites.yml}
metadata:
  type: reference
---

# Audits par module — remplacé (v1 → v2, 02/10/2026)

La v1 de ce fichier (BLOC COMMUN + 14 déclencheurs de deux mots) est **remplacée le 02/10/2026** par :

- le skill **`.claude/skills/audit/SKILL.md`** — commande opérationnelle : `audit first`, `audit next`,
  `continue audit`, `loop audit`, `audit status`, `audit <mot>`, `vérifie <GROUPE>` ;
- **`docs/audits/METHODE.md`** — la méthode (critères C1-C14, phases 0-6, formats constat / tâche,
  clôture, propriété et routage des tâches vers `docs/plans/PLAN_AUDIT_<UNITE>.md`) ;
- **`docs/audits/unites.yml`** — le registre partagé des 19 unités classées (chemins possédés, coutures,
  score, niveau, statut, groupe, plans alimentés), lu sur `origin/main` depuis n'importe quel poste.

Les anciens mots (`leads`, `fiche`, `cadence`, `clients`, `visites`, `calepinage`, `devis`,
`facturation`, `stock`, `chantiers`, `sav`, `ged`, `portail`, `parametres`) restent acceptés et se
résolvent selon **METHODE.md §D.4**. Le texte v1 complet reste dans l'historique git de ce fichier.
