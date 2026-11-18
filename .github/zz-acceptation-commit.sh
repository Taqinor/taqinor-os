#!/usr/bin/env bash
# TEMPORAIRE (zz-scratch-acceptation-taches-f3) — commite l'enregistrement d'acceptation produit par le job sur la branche
# (copie du précédent du 17/11). Une poussée faite avec GITHUB_TOKEN ne relance aucun workflow.
set -uo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A docs/audits/acceptation docs/qa-explorer/captures 2>/dev/null
if git diff --cached --quiet; then echo "rien a commiter"; exit 0; fi
git commit -q -m "acceptation Taches F3 — enregistrement du job $1 (run ${GITHUB_RUN_ID}, sha ${GITHUB_SHA:0:9})"
for i in 1 2 3 4 5; do
  if git push -q origin "HEAD:${GITHUB_REF_NAME}"; then echo "pousse"; exit 0; fi
  git pull -q --rebase origin "${GITHUB_REF_NAME}" || { git rebase --abort; sleep 5; }
  sleep $((i * 3))
done
echo "poussee impossible"; exit 1
