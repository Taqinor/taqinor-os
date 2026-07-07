<#
WOW25 — nettoyage de l'espace de travail (worktrees + branches + cache docker).

Mesuré le 2026-07-08 : 607 worktrees (~40 Go), 1 028 branches (583 debris
`agent-*`/`claude/*`), 12,5 Go de cache de build docker. Ce debris ralentit
CHAQUE operation git et sature le disque.

SÛR PAR DÉFAUT : ne supprime JAMAIS un worktree qui a des changements non
commites (il est listé, pas touché) ni une branche NON mergée dans main (listée).
Passe -WhatIf pour un essai à blanc (rien n'est supprimé, tout est listé).

Usage :  powershell -File scripts\gc-workspace.ps1 [-WhatIf] [-MaxAgeDays 14]
#>
param(
  [switch]$WhatIf,
  [int]$MaxAgeDays = 14
)
$ErrorActionPreference = 'Stop'
$repo = (git -C $PSScriptRoot/.. rev-parse --show-toplevel)
Set-Location $repo
$act = if ($WhatIf) { '[dry-run] ' } else { '' }
Write-Host "== gc-workspace ($act mode) — repo $repo =="

# 1) Worktrees : prune les référence mortes, puis supprime les dossiers
#    .claude/worktrees/* enregistrés, plus vieux que MaxAgeDays ET propres.
git worktree prune
$cutoff = (Get-Date).AddDays(-$MaxAgeDays)
$registered = (git worktree list --porcelain | Select-String '^worktree ' | ForEach-Object { $_.ToString().Substring(9) })
$removed = 0; $kept = 0
foreach ($it in (Get-ChildItem "$repo/.claude/worktrees" -Directory -ErrorAction SilentlyContinue)) {
  $p = $it.FullName
  $dirty = $false
  try { $dirty = [bool](git -C $p status --porcelain 2>$null) } catch { $dirty = $true }
  if ($dirty) { Write-Host "  KEEP (dirty)   $($it.Name)"; $kept++; continue }
  if ($it.LastWriteTime -gt $cutoff) { Write-Host "  KEEP (recent)  $($it.Name)"; $kept++; continue }
  Write-Host "  ${act}REMOVE worktree $($it.Name)"
  if (-not $WhatIf) {
    git worktree remove --force $p 2>$null
    if (Test-Path $p) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue }
    $removed++
  }
}
git worktree prune

# 2) Branches locales fusionnées dans main, motif agent-*/claude/* → suppr.
#    Non-mergées → listées, jamais supprimées.
$mergedDeleted = 0; $unmergedKept = @()
$merged = (git branch --merged main --format '%(refname:short)') -split "`n" | Where-Object { $_ -and $_ -notin @('main','master') -and ($_ -match '^(agent-|claude/|wow-)') }
foreach ($b in $merged) {
  Write-Host "  ${act}delete merged branch $b"
  if (-not $WhatIf) { git branch -D $b 2>$null | Out-Null; $mergedDeleted++ }
}
$unmergedKept = (git branch --no-merged main --format '%(refname:short)') -split "`n" | Where-Object { $_ -and ($_ -match '^(agent-|claude/|wow-)') }
if ($unmergedKept) { Write-Host "  KEEP (non fusionnées, à vérifier à la main) :"; $unmergedKept | ForEach-Object { Write-Host "    - $_" } }

# 3) Docker : cache de build + images pendantes.
Write-Host "  ${act}docker builder prune + dangling images"
if (-not $WhatIf) { docker builder prune -f 2>$null | Out-Null; docker image prune -f 2>$null | Out-Null }

$wtLeft = (git worktree list | Measure-Object).Count
$brLeft = (git branch | Measure-Object).Count
$ukCount = $unmergedKept.Count
Write-Host ""
Write-Host "== Resume =="
Write-Host "  worktrees supprimes : $removed  (gardes : $kept)"
Write-Host "  branches fusionnees supprimees : $mergedDeleted  (non-fusionnees gardees : $ukCount)"
Write-Host "  worktrees restants : $wtLeft  |  branches locales : $brLeft"
