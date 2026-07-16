# Séquence d'atterrissage de fin de plan-run — la même suite d'étapes qu'un
# agent doit exécuter à la main avant de merger dev -> main. On en fait un
# script, pas une discipline d'agent : le fingerprint CODEMAP périmé revient
# régulièrement en rouge CI, et chaque occurrence coûte un cycle CI complet
# (~40 min, voir CLAUDE.md § COST MODEL). Ce script élimine la classe d'erreur.
#
# End-of-plan-run landing sequence — the same steps an agent must run by hand
# before merging dev -> main. Made a script, not agent discipline: the stale
# CODEMAP fingerprint CI red recurs and each occurrence costs a full CI cycle
# (~40 min, see CLAUDE.md § COST MODEL). This script eliminates that error
# class entirely.
#
# Étapes, dans l'ordre, chacune interrompant le script en cas d'échec :
# Steps, in order, each aborting the script on failure:
#   (a) git fetch origin + git merge origin/main --no-edit
#   (b) python scripts/codemap_fingerprint.py --write
#   (c) python scripts/check_stages.py
#   (d) python scripts/codemap_fingerprint.py --check   (doit être vert)
#   (e) commit du re-stamp CODEMAP si (et seulement si) il a changé
#       (idempotent — un deuxième run ne doit PAS créer de commit vide)
#   (f) git push
#
# Usage :
#   powershell -File scripts\land.ps1

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

function Step-Header([string]$Label) {
    Write-Host ""
    Write-Host "── $Label ──" -ForegroundColor Cyan
}

function Invoke-Checked([string]$Description, [scriptblock]$Action) {
    Step-Header $Description
    & $Action
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        Write-Host "✗ ÉCHEC : $Description (code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

try {
    Write-Host "=== Séquence d'atterrissage (land.ps1) ===" -ForegroundColor Green

    # ── (a) fetch + merge origin/main ───────────────────────────────────────
    Invoke-Checked "git fetch origin" { git fetch origin }

    Step-Header "git merge origin/main --no-edit"
    git merge origin/main --no-edit
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "✗ CONFLIT DE MERGE avec origin/main." -ForegroundColor Red
        Write-Host "  Résolvez les conflits manuellement, puis relancez ce script." -ForegroundColor Red
        Write-Host "  (Le merge est resté en cours — 'git status' pour le détail.)" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK — à jour avec origin/main."

    # ── (b) re-stamp le fingerprint CODEMAP ─────────────────────────────────
    Invoke-Checked "python scripts/codemap_fingerprint.py --write" {
        python scripts/codemap_fingerprint.py --write
    }

    # ── (c) check_stages.py ─────────────────────────────────────────────────
    Invoke-Checked "python scripts/check_stages.py" {
        python scripts/check_stages.py
    }

    # ── (d) codemap_fingerprint.py --check (doit être vert) ────────────────
    Invoke-Checked "python scripts/codemap_fingerprint.py --check" {
        python scripts/codemap_fingerprint.py --check
    }

    # ── (e) commit du re-stamp si (et seulement si) CODEMAP.md a changé ────
    # Idempotent : relancer ce script sans changement réel ne doit PAS créer
    # de commit vide. Idempotent: re-running this script with no real change
    # must NOT create an empty commit.
    Step-Header "Commit du re-stamp CODEMAP (si nécessaire)"
    $codemapStatus = git status --porcelain docs/CODEMAP.md
    if ($codemapStatus -and $codemapStatus.Trim().Length -gt 0) {
        git add docs/CODEMAP.md
        git commit -m "chore(land): re-stamp CODEMAP fingerprint"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ ÉCHEC : commit du re-stamp CODEMAP" -ForegroundColor Red
            exit $LASTEXITCODE
        }
        Write-Host "  Commit créé : chore(land): re-stamp CODEMAP fingerprint"
    } else {
        Write-Host "  docs/CODEMAP.md inchangé — rien à commiter (idempotent, OK)."
    }

    # ── (f) push ─────────────────────────────────────────────────────────────
    Invoke-Checked "git push" { git push }

    Write-Host ""
    Write-Host "=== Atterrissage terminé avec succès. ===" -ForegroundColor Green
}
finally {
    Pop-Location
}
