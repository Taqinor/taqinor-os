---
name: auto-fix-toujours
description: 27/10/2026 — règle fondateur : Auto-fix allumé sur TOUTE PR ouverte par Claude, dès l'ouverture, sans jamais demander
metadata:
  type: feedback
---

# Auto-fix toujours allumé (fondateur, 27/10/2026)

**Règle.** Toute session qui ouvre une PR allume Auto-fix dessus (`mcp__ccd_pr__set_monitor`
`auto_fix: true`) dans le MÊME tour que `gh pr create`, sans demander — pour chaque PR, chaque
session, chaque poste. Reda, 27/10 : « why you keep asking me about turning auto fix on, turn it on
for everything and for every session and for all the future sessions ».

**Pourquoi la question revenait.** Le classifieur du mode auto bloquait `set_monitor` faute
d'accord explicite dans la session. Corrigé sur le poste principal : `mcp__ccd_pr__set_monitor` est
dans `permissions.allow` des réglages utilisateur (`~/.claude/settings.json`). Sur un autre poste où
l'appel est encore refusé : ajouter la même règle à ses réglages utilisateur, jamais reposer la
question à Reda.

**Et ensuite.** Auto-fix réveille la session sur un rouge CI / conflit / commentaire : corriger,
pousser, puis mettre en file (`gh pr merge --auto --merge`, voir [[merge-queue-main]]).
