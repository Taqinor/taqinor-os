#!/usr/bin/env bash
# Wake-up routine (Fable monitoring audit, 27/10 13:10 UTC). Usage: wake.sh [minutes-to-wait-first]
# 1) open PRs: mergeable / queued / CI fails / last commit age; CONFLICTING → files in conflict (docs-only?)
# 2) stale L3 branches (> 60 min without commit and PR not merged) → RELANCER
# 3) PRs merged since last wake: sent-quote gate grep + « Décision prise pour le fondateur » harvest
SP="$(cd "$(dirname "$0")" && pwd)"
REPO="C:/dev/taqinor-os/.claude/worktrees/bakery-quote-pricing-1e22b4"
cd "$REPO" || exit 1
if [ -n "$1" ]; then end=$(( $(date +%s) + $1*60 )); until [ $(date +%s) -ge $end ]; do sleep 30; done; fi
MARK="$SP/last_wake"; SINCE=$(cat "$MARK" 2>/dev/null || echo "2026-10-27T12:40:00Z"); now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
git fetch -q origin 2>/dev/null
echo "=== WAKE $(date -u +%H:%M) UTC (since $SINCE) ==="
echo "--- MERGE QUEUE (authoritative; autoMergeRequest reads null once queued) ---"
timeout 90 gh api graphql -f query='{ repository(owner:"Taqinor", name:"taqinor-os") { mergeQueue(branch:"main") { entries(first:20) { nodes { position state estimatedTimeToMerge pullRequest { number } } } } } }' \
  -q '.data.repository.mergeQueue.entries.nodes[] | "  pos \(.position) \(.state) PR#\(.pullRequest.number) eta \(.estimatedTimeToMerge // "-")s"' 2>/dev/null
echo "--- OPEN PRs (NOT-queued = no auto-merge flag; check the queue above before acting) ---"
timeout 90 gh pr list --state open --limit 80 --json number,title,mergeable,headRefName,autoMergeRequest,updatedAt \
  -q '.[] | select(.headRefName | startswith("dependabot/") | not) | "\(.number)\t\(.mergeable)\t\(if .autoMergeRequest then "queued" else "NOT-queued" end)\t\(.headRefName)\t\(.title[:48])"' > "$SP/prs.tsv"
while IFS=$'\t' read -r n m q br t; do
  age=""; ts=$(git log -1 --format=%ct "origin/$br" 2>/dev/null); [ -n "$ts" ] && age=$(( ($(date +%s) - ts) / 60 ))
  fails=$(timeout 60 gh pr checks "$n" 2>/dev/null | awk -F'\t' '$2=="fail"{print $1}' | tr '\n' ',' | sed 's/,$//')
  flag=""; [ "$m" = "CONFLICTING" ] && flag=" CONFLICT"; [ -n "$age" ] && [ "$age" -gt 60 ] && [ "$m" != "MERGED" ] && flag="$flag STALE(${age}m)"
  echo "#$n $m $q ${age}m-old [$br] $t${fails:+ RED:$fails}$flag"
  if [ "$m" = "CONFLICTING" ]; then
    git merge-tree --write-tree --name-only origin/main "origin/$br" 2>/dev/null | sed '1d' | grep -v '^$' | sed 's/^/      conflict: /' | head -8
  fi
done < "$SP/prs.tsv"
echo "--- MERGED since last wake ---"
timeout 90 gh pr list --state merged --limit 20 --json number,title,mergedAt,mergeCommit,body \
  -q ".[] | select(.mergedAt > \"$SINCE\") | \"\(.number)\t\(.mergeCommit.oid)\t\(.mergedAt[11:16])\t\(.title[:48])\"" > "$SP/merged.tsv"
while IFS=$'\t' read -r n sha at t; do
  echo "#$n $at $t"
  git diff "$sha^1" "$sha" 2>/dev/null | grep -n '^[+-].*\(calcul_corrige\|regles_au_moins\|regles_origine\)' | head -5 | sed 's/^/      gate: /'
  timeout 60 gh pr view "$n" --json body -q .body 2>/dev/null | grep -i 'décision prise pour le fondateur' | sed "s/^/      D(#$n): /" | head -5 >> "$SP/decisions_fondateur.txt"
done < "$SP/merged.tsv"
echo "--- decisions harvested so far: $(wc -l < "$SP/decisions_fondateur.txt" 2>/dev/null || echo 0) lines ---"
echo "$now" > "$MARK"
