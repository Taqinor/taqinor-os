---
name: merge-queue-main
description: 09/10/2026 — main est derrière une merge queue GitHub (ruleset) ; gh pr merge --auto --merge met en file, plus jamais de boucle update-branch ; CI répond à merge_group
metadata:
  type: project
---

# Merge queue sur `main` (fondateur, 09/10/2026)

**Fait.** Reda a demandé « enable github merge [queue] » après la PR #907 : trois `gh pr update-branch`
d'affilée, à chaque fois dépassée par un merge de l'autre PC (une lane toutes les 20-40 min) alors que la
protection exigeait « à jour avec main » + runners saturés. La file remplace cette course : chaque PR est
reconstruite sur `main` + les PR devant elle, ses checks requis tournent sur ce groupe, puis GitHub merge seul.

**Mécanique.**
- Ruleset « merge queue main » (Settings → Rules → Rulesets) : méthode MERGE, ALLGREEN, 5 entrées max,
  délai des checks 90 min, aucun contournement. La protection classique (6 checks requis, 0 approbation)
  reste en place.
- `.github/workflows/ci.yml` répond à `merge_group` ; le détecteur `changes` diffe `merge_group.base_sha`
  → `head_sha` (docs-only reste docs-only dans la file).
- Entrée en file : `gh pr merge <n> --auto --merge` (ou le bouton « Merge when ready »). `--delete-branch`
  ne marche pas depuis un worktree (« 'main' is already used by worktree ») : supprimer la branche après.

**Why:** une PR verte ne doit plus repartir en CI parce qu'une autre a mergé entre-temps.

**How to apply:** plus jamais de boucle `gh pr update-branch` → CI → merge ; une PR retirée de la file
(checks rouges sur le groupe) se corrige puis se remet en file. Voir [[check-main-before-fixing]].
