---
name: audits-modules
description: La commande « audit » est en v3 depuis le 09/10/2026 — METHODE.md v3, skill audit, registre, decisions.yml, tâches v3 aux clauses calculées, boucle de clôture mécanique, audits par parcours
metadata:
  type: project
---

**La commande « audit » suit `docs/audits/METHODE.md` v3 (09/10/2026)** — skill `.claude/skills/audit/SKILL.md`, registre
`docs/audits/unites.yml` (champ `dossier:`, statuts calculés), décisions `docs/audits/decisions.yml`, gabarit
`docs/audits/GABARIT_DOSSIER.md`, premier dossier v3 `docs/audits/2026-10-09-methode.md`.

- **Pourquoi v3 (mesuré) :** 48 % des tâches d'audit cochées étaient corrigées en un coup ; 0 des 19 acceptations live jouées,
  0 `vérifie`, registre figé ; +17 % de code en 7 jours ; 32 % des tâches routées hors unité ; aucun critère de parcours.
- **Tâche v3 :** une ligne, 14 clauses dont Emplacement / Code net / Appelants / Assertions existantes / Jumeaux / Listes
  figées / Contrat partagé CALCULÉES (générateur `scripts/audit_tache.py`, AMET à construire ; d'ici là greps collés),
  `n/a — raison` obligatoire, `@model` obligatoire, ancre `fichier::symbole`, test dans le module EXISTANT. Les tâches v2
  ouvertes sont gelées dans `scripts/taches_audit_v2.txt` (ne fait que rétrécir) ; FORME 5 de `check_taches_cablage.py`
  juge v2 ou v3 selon la liste.
- **Clôture :** acceptation = couverture par tâche (`docs/audits/acceptation/<G>/…`, jouée par l'orchestrateur du plan-run,
  CLAUDE.md 3-bis) ; `vérifie <G>` dû à 50 % / 95 % ; écarts sous `### <G> — ÉCARTS vérifie <date> · format v3` chez le
  propriétaire ; sondes au dépôt `docs/audits/sondes/<G>/`.
- **Parcours :** PA1-PA7 + PF1-PF3 (METHODE §D.1), tables `apps/<pilote>/parcours/<PA>.json`, critères C15-C20.
- **Propriété :** fusion crm→lead et générateur→devis approuvée (D-OWN-FUSION, PR dédiée) ; TRANSVERSE = SPL `(@atomique: …)`.

**Why:** Reda (09/10/2026) : des tâches qui corrigent en un coup, un ERP de parcours automatiques modifiables à chaque
étape, un code non répété, les travers d'un ERP écrit par LLM détectés, le découpage ré-examiné.

**How to apply:** tout audit, `vérifie` et plan-run d'un groupe d'audit suit METHODE v3 ; un écart est amendé dans la même PR.
Voir [[propriete-fichiers]], [[lecons-construction-qjr5]].
