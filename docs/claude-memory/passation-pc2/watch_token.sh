#!/usr/bin/env bash
# Surveille la PR porteuse du jeton CI ; sort dès qu'un événement demande la coordinatrice.
# Usage: watch_token.sh <pr> [max_minutes=60] [sha-rouge-connu]
PR="$1"; MAX=${2:-60}; KNOWN_RED="${3:-}"; cd "C:/dev/taqinor-os/.claude/worktrees/passation-pc2-l3-devis-fa13c5" || exit 1
end=$(( $(date +%s) + MAX*60 ))
queue() { timeout 60 gh api graphql -f query='{ repository(owner:"Taqinor", name:"taqinor-os") { mergeQueue(branch:"main") { entries(first:20) { nodes { position state pullRequest { number } } } } } }' -q '.data.repository.mergeQueue.entries.nodes[] | "pos \(.position) \(.state) PR#\(.pullRequest.number)"' 2>/dev/null; }
while [ $(date +%s) -lt $end ]; do
  st=$(timeout 60 gh pr view "$PR" --json state,mergeable -q '"\(.state) \(.mergeable)"' 2>/dev/null)
  q=$(queue); mine=$(echo "$q" | grep "PR#$PR\$")
  fails=$(timeout 60 gh pr checks "$PR" 2>/dev/null | awk -F'\t' '$2=="fail"{print $1}' | tr '\n' ',' | sed 's/,$//')
  case "$st" in
    MERGED*)   echo "TOKEN-EVENT $(date -u +%H:%M) PR#$PR MERGED → jeton au suivant"; exit 0 ;;
    CLOSED*)   echo "TOKEN-EVENT $(date -u +%H:%M) PR#$PR CLOSED (non mergée)"; exit 0 ;;
  esac
  head=$(timeout 60 gh pr view "$PR" --json headRefOid -q .headRefOid 2>/dev/null | cut -c1-9)
  if [ -n "$fails" ] && [ -n "$KNOWN_RED" ] && [ "$head" = "$KNOWN_RED" ]; then fails=""; fi
  if [ -n "$fails" ]; then echo "TOKEN-EVENT $(date -u +%H:%M) PR#$PR RED: $fails (state $st; queue: ${mine:-not in queue})"; exit 0; fi
  if echo "$mine" | grep -q UNMERGEABLE; then echo "TOKEN-EVENT $(date -u +%H:%M) PR#$PR UNMERGEABLE in queue ($st)"; echo "$q"; exit 0; fi
  auto=$(timeout 60 gh pr view "$PR" --json autoMergeRequest -q '.autoMergeRequest != null' 2>/dev/null)
  if [ -z "$mine" ] && [ "$auto" = "false" ]; then
    grp=$(timeout 60 gh run list --workflow ci.yml --event merge_group --limit 20 --json headBranch,conclusion,databaseId,createdAt -q ".[] | select(.headBranch | contains(\"pr-$PR-\")) | \"\(.createdAt[11:16]) \(.conclusion) \(.databaseId)\"" 2>/dev/null | head -3 | tr '\n' ';')
    echo "TOKEN-EVENT $(date -u +%H:%M) PR#$PR EJECTED from queue (auto-merge off, PR checks: ${fails:-green}); group runs: ${grp:-none}"; exit 0
  fi
  sleep 90
done
echo "TOKEN-WATCH $(date -u +%H:%M) PR#$PR still open after ${MAX} min: $st; queue: ${mine:-not in queue}; $(queue | tr '\n' ' ')"
