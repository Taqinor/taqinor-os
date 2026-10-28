#!/usr/bin/env bash
# Point toutes les 10 min (PC2). Usage: wake.sh [minutes-to-wait-first]
# 1) garde machine ; 2) jeton CI inter-PC ; 3) file de merge + PR ouvertes claude/* ; 4) PR mergées depuis le dernier point ; 5) état des lanes
SP="$(cd "$(dirname "$0")" && pwd)"
REPO="C:/dev/taqinor-os/.claude/worktrees/passation-pc2-l3-devis-fa13c5"
cd "$REPO" || exit 1
if [ -n "$1" ]; then end=$(( $(date +%s) + $1*60 )); until [ $(date +%s) -ge $end ]; do sleep 30; done; fi
MARK="$SP/last_wake"; SINCE=$(cat "$MARK" 2>/dev/null || echo "2026-10-27T23:40:00Z"); now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
git fetch -q origin 2>/dev/null
bash "$SP/guard.sh"
echo "=== WAKE $(date -u +%H:%M) UTC (since $SINCE) ==="
echo "--- JETON CI (claims) ---"
timeout 90 python scripts/plan_claims.py list 2>/dev/null | grep -i "jeton" || echo "  app:jeton-ci: ABSENT"
echo "--- MERGE QUEUE ---"
timeout 90 gh api graphql -f query='{ repository(owner:"Taqinor", name:"taqinor-os") { mergeQueue(branch:"main") { entries(first:20) { nodes { position state estimatedTimeToMerge pullRequest { number } } } } } }' \
  -q '.data.repository.mergeQueue.entries.nodes[] | "  pos \(.position) \(.state) PR#\(.pullRequest.number) eta \(.estimatedTimeToMerge // "-")s"' 2>/dev/null
echo "--- OPEN PRs claude/* ---"
timeout 90 gh pr list --state open --limit 80 --json number,title,mergeable,headRefName,autoMergeRequest \
  -q '.[] | select(.headRefName | startswith("claude/")) | "\(.number)\t\(.mergeable)\t\(if .autoMergeRequest then "auto" else "no-auto" end)\t\(.headRefName)\t\(.title[:48])"' > "$SP/prs.tsv"
while IFS=$'\t' read -r n m q br t; do
  age=""; ts=$(git log -1 --format=%ct "origin/$br" 2>/dev/null); [ -n "$ts" ] && age=$(( ($(date +%s) - ts) / 60 ))
  fails=$(timeout 60 gh pr checks "$n" 2>/dev/null | awk -F'\t' '$2=="fail"{print $1}' | tr '\n' ',' | sed 's/,$//')
  flag=""; [ "$m" = "CONFLICTING" ] && flag=" CONFLICT"
  echo "#$n $m $q ${age}m-old [$br] $t${fails:+ RED:$fails}$flag"
done < "$SP/prs.tsv"
echo "--- MERGED since last wake ---"
timeout 90 gh pr list --state merged --limit 20 --json number,title,mergedAt,mergeCommit,body \
  -q ".[] | select(.mergedAt > \"$SINCE\") | \"\(.number)\t\(.mergeCommit.oid)\t\(.mergedAt[11:16])\t\(.title[:48])\"" > "$SP/merged.tsv"
while IFS=$'\t' read -r n sha at t; do
  echo "#$n $at $t"
  git diff "$sha^1" "$sha" 2>/dev/null | grep -n '^[+-].*\(calcul_corrige\|regles_au_moins\|regles_origine\)' | head -5 | sed 's/^/      gate: /'
  timeout 60 gh pr view "$n" --json body -q .body 2>/dev/null | grep -i 'décision prise pour le fondateur' | sed "s/^/      D(#$n): /" | head -5 >> "$SP/decisions_fondateur_harvest.txt"
done < "$SP/merged.tsv"
echo "--- ETAT des lanes ($SP/etat) ---"
for f in "$SP"/etat/*.md; do [ -f "$f" ] && echo "  $(basename "$f" .md): $(grep -m1 '^ETAT:' "$f" 2>/dev/null || head -1 "$f")"; done
echo "$now" > "$MARK"
