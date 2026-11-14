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

- Branche `claude/*` (session cloud) : la CI de la PR est « allégée » (`allege=true` du détecteur `changes`) — les
  suites lourdes (tests backend, vitest, e2e) ne tournent QUE sur le groupe de la file. Ne pas les attendre sur la
  PR : lancer `--auto --merge` dès les contrôles rapides verts ; le groupe a pris 15 min le 14/11/2026 (PR #1397).
- Une PR en CONFLIT avec `main` ne déclenche AUCUNE CI (seul `dependabot-automerge` apparaît) : si rien ne démarre
  après une poussée, fusionner `main` d'abord. Les plans d'audit sont le point de friction quand une autre session
  y écrit : garder ses ajouts hors de la queue du fichier et quelques lignes sous `## DONE LOG`.

**Why:** une PR verte ne doit plus repartir en CI parce qu'une autre a mergé entre-temps.

**How to apply:** plus jamais de boucle `gh pr update-branch` → CI → merge ; une PR retirée de la file
(checks rouges sur le groupe) se corrige puis se remet en file. Voir [[check-main-before-fixing]].
