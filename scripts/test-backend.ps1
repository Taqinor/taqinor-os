# La SEULE façon canonique de lancer les tests Django backend en local contre
# la pile docker. Ne PAS improviser une commande `docker compose run` à la main
# — ce script encapsule la garde single-writer (voir plus bas) qui a évité une
# corruption de la base de test à deux reprises.
#
# The ONE canonical way to run backend Django tests locally against the docker
# stack. Do NOT hand-roll a `docker compose run` — this script encapsulates the
# single-writer guard below, which has already prevented test-DB corruption
# twice.
#
# Usage :
#   powershell -File scripts\test-backend.ps1
#   powershell -File scripts\test-backend.ps1 -Modules "apps.crm apps.ventes" -Parallel 8
#   powershell -File scripts\test-backend.ps1 -RebuildDb        # voir AVERTISSEMENT plus bas
#
# Par défaut : --keepdb (rapide, réutilise test_erp_db entre les runs).
# -RebuildDb : DROP test_erp_db avant de lancer — Django la recrée à froid.
#
# GARDE SINGLE-WRITER (critique) : test_erp_db est une base UNIQUE partagée par
# tout ce qui tourne dans docker compose (pas de writer concurrent). Deux runs
# simultanés se sont déjà marché dessus et ont corrompu la base de test — ce
# script REFUSE de démarrer si un conteneur de run backend-tests est déjà actif.
#
# SINGLE-WRITER GUARD (critical): test_erp_db is a single shared database — no
# concurrent writer. Two simultaneous runs have already collided and corrupted
# it — this script REFUSES to start if a backend-tests run container is already
# active.

param(
    [string]$Modules = "apps authentication core",
    [int]$Parallel = 4,
    [switch]$RebuildDb
)

$ErrorActionPreference = 'Stop'

# Se placer à la racine du dépôt (le docker-compose.yml y vit) — the compose
# files live at repo root, not under scripts/.
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    $ComposeProject = 'erp-agentique'
    $DbContainer = 'erp-agentique-db-1'
    $DbUser = 'erp_user'
    $AdminDb = 'erp_db'
    $TestDb = 'test_erp_db'
    $RunNamePattern = 'erp-agentique-django_core-run'

    # ── GARDE SINGLE-WRITER / SINGLE-WRITER GUARD ──────────────────────────
    # Vérifie qu'aucun autre run de tests backend n'est déjà en cours avant de
    # toucher test_erp_db. Check for any other backend test run already active
    # before touching test_erp_db.
    Write-Host "→ Vérification qu'aucun autre run de tests backend n'est actif…"
    $existing = docker ps --filter "name=$RunNamePattern" --format '{{.Names}}'
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Impossible d'interroger docker (docker ps a échoué). Docker Desktop tourne-t-il ?"
        exit 1
    }
    if ($existing -and $existing.Trim().Length -gt 0) {
        Write-Host ""
        Write-Host "REFUS DE DÉMARRER : un run de tests backend est déjà actif :" -ForegroundColor Red
        Write-Host "  $existing" -ForegroundColor Red
        Write-Host ""
        Write-Host "test_erp_db est single-writer — deux runs simultanés l'ont déjà" -ForegroundColor Red
        Write-Host "corrompue par le passé. Attendez la fin de l'autre run, ou tuez-le :" -ForegroundColor Red
        Write-Host "  docker rm -f $existing" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
    Write-Host "  OK — aucun run concurrent détecté."

    # ── -RebuildDb : DROP + AVERTISSEMENT / DROP + WARNING ─────────────────
    if ($RebuildDb) {
        Write-Host ""
        Write-Host "==============================================================" -ForegroundColor Yellow
        Write-Host " AVERTISSEMENT — REBUILD COMPLET DE test_erp_db" -ForegroundColor Yellow
        Write-Host " Un rebuild complet peut prendre PLUSIEURS HEURES sur ce PC." -ForegroundColor Yellow
        Write-Host " Ne lancez ceci QUE seul, de nuit, sans autre run en parallèle." -ForegroundColor Yellow
        Write-Host ""
        Write-Host " WARNING — FULL REBUILD OF test_erp_db" -ForegroundColor Yellow
        Write-Host " A full rebuild can take HOURS on this box. Run this ALONE," -ForegroundColor Yellow
        Write-Host " overnight, with no other run in parallel." -ForegroundColor Yellow
        Write-Host "==============================================================" -ForegroundColor Yellow
        Write-Host ""

        Write-Host "→ DROP DATABASE test_erp_db (avec terminaison des connexions actives)…"
        $dropSql = @"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TestDb' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS $TestDb;
"@
        docker exec $DbContainer psql -U $DbUser -d $AdminDb -c $dropSql
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Échec du DROP DATABASE $TestDb — le conteneur $DbContainer tourne-t-il ?"
            exit 1
        }
        Write-Host "  test_erp_db supprimée — sera recréée à froid par ce run."
        $KeepDbFlag = @()
    } else {
        $KeepDbFlag = @('--keepdb')
    }

    # ── Commande de test / test command ────────────────────────────────────
    $ModulesList = $Modules -split '\s+' | Where-Object { $_ -ne '' }
    $testArgs = @(
        'compose', '-p', $ComposeProject, 'run', '--rm', '--no-deps',
        '-e', 'DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev',
        'django_core',
        'python', 'manage.py', 'test'
    ) + $ModulesList + $KeepDbFlag + @('--parallel', "$Parallel", '-v1')

    Write-Host ""
    Write-Host "→ docker $($testArgs -join ' ')"
    Write-Host ""

    & docker @testArgs
    $testExitCode = $LASTEXITCODE

    Write-Host ""
    if ($testExitCode -eq 0) {
        Write-Host "✓ Tests backend : SUCCÈS (modules: $Modules)" -ForegroundColor Green
    } else {
        Write-Host "✗ Tests backend : ÉCHEC (code $testExitCode, modules: $Modules)" -ForegroundColor Red
    }

    exit $testExitCode
}
finally {
    Pop-Location
}
