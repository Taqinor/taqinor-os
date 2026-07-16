# scripts/watch-ci.ps1 - wait for the current branch's CI run (or a named PR's
# checks) to reach a terminal state, then print a per-job PASS/FAIL summary and
# exit with CI's own status. The canonical "what happened to my push" command.
#
# WHY (2026-07-11): a plan run repeatedly hand-rolled its own waiters/monitors to
# sit on the ~40-min CI wait, and hand-rolled `gh ... 2>&1 | tail` status checks
# that MASK the real exit code (tail's 0 hides gh's failure) -> false greens it
# then chased. This wraps `gh run watch --exit-status` once so no session re-invents
# either footgun. Exit code is CI's: 0 = all green, non-zero = something failed.
#
# Usage:
#   powershell -File scripts/watch-ci.ps1            # watch HEAD of the current branch
#   powershell -File scripts/watch-ci.ps1 -Pr 362    # watch a specific PR's checks
#   powershell -File scripts/watch-ci.ps1 -Sha abc123
param(
    [int]$Pr = 0,
    [string]$Sha = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Host "gh (GitHub CLI) is not installed / not on PATH." -ForegroundColor Red
        exit 1
    }

    # PR mode: gh already has a purpose-built watcher that exits non-zero on failure.
    if ($Pr -gt 0) {
        gh pr checks $Pr --watch
        exit $LASTEXITCODE
    }

    if (-not $Sha) { $Sha = (git rev-parse HEAD).Trim() }
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()

    # The Actions run for a just-pushed SHA may not be registered instantly - retry.
    $runId = $null
    for ($i = 1; $i -le 10; $i++) {
        $out = gh run list --commit $Sha --branch $branch --limit 1 --json databaseId 2>$null
        if ($out) {
            $parsed = $out | ConvertFrom-Json
            if ($parsed -and $parsed.Count -gt 0) { $runId = $parsed[0].databaseId; break }
        }
        Write-Host "Waiting for the CI run for $Sha to appear ($i/10)..."
        Start-Sleep -Seconds 6
    }
    if (-not $runId) {
        Write-Host "No CI run found for $Sha on $branch (pushed yet?)." -ForegroundColor Red
        exit 1
    }

    Write-Host "-> Watching CI run $runId ($branch @ $($Sha.Substring(0,8)))..." -ForegroundColor Cyan
    gh run watch $runId --exit-status --interval 15
    $watch = $LASTEXITCODE

    Write-Host ""
    Write-Host "=== job summary (run $runId) ===" -ForegroundColor Cyan
    # Per-job conclusion; never piped through tail, so nothing masks a failure.
    # \t is passed literally to jq (single-quoted here), which renders it as a tab.
    gh run view $runId --json jobs --jq '.jobs[] | "\(.conclusion // .status)\t\(.name)"'

    Write-Host ""
    if ($watch -eq 0) {
        Write-Host "OK - CI green. Safe to merge/deploy." -ForegroundColor Green
    } else {
        Write-Host "FAILED - a required check did not pass (see summary above). Fix-forward, do not merge." -ForegroundColor Red
    }
    exit $watch
}
finally {
    Pop-Location
}
