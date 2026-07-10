# La SEULE facon canonique de lancer les tests Django backend en local contre
# la pile docker. Ne PAS improviser une commande `docker compose run` a la main
# — ce script encapsule la garde single-writer (voir plus bas) qui a evite une
# corruption de la base de test a deux reprises.
#
# The ONE canonical way to run backend Django tests locally against the docker
# stack. Do NOT hand-roll a `docker compose run` — this script encapsulates the
# single-writer guard below, which has already prevented test-DB corruption twice.
#
# Usage :
#   powershell -File scripts\test-backend.ps1
#   powershell -File scripts\test-backend.ps1 -Modules "apps.crm apps.ventes" -Parallel 8
#   powershell -File scripts\test-backend.ps1 -Snapshot     # fige la base migree actuelle comme TEMPLATE de base
#   powershell -File scripts\test-backend.ps1 -RestoreDb    # WOW8-local : clone le TEMPLATE (~secondes) puis migre l'increment
#   powershell -File scripts\test-backend.ps1 -RebuildDb    # rebuild a froid — DERNIER RECOURS, voir AVERTISSEMENT
#
# POURQUOI -RestoreDb / -Snapshot (WOW8 en local, 2026-07-10) : construire la
# base de test a froid, c'est rejouer ~850 migrations = ~35 min, et un run de
# plan qui refait ca a CHAQUE gate (collisions de migrations, clones perimes,
# OOM en cours de build) a deja brule des HEURES. La parade est identique a WOW8
# cote CI : on garde une base `test_erp_db_base` deja migree, et -RestoreDb la
# CLONE par TEMPLATE Postgres (quasi instantane) au lieu de tout reconstruire ;
# `--keepdb` n'applique alors que les migrations ajoutees depuis le snapshot.
# Apres une build a froid propre, lancer -Snapshot pour rafraichir le TEMPLATE.
#
# GARDE SINGLE-WRITER (critique) : test_erp_db est une base UNIQUE partagee par
# tout ce qui tourne dans docker compose. Deux runs simultanes se sont deja
# marche dessus et ont corrompu la base — ce script REFUSE de demarrer si un
# conteneur de run backend-tests est deja actif.

param(
    [string]$Modules = "apps authentication core",
    [int]$Parallel = 4,
    [switch]$RebuildDb,
    [switch]$RestoreDb,
    [switch]$Snapshot
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    $ComposeProject = 'erp-agentique'
    $DbContainer = 'erp-agentique-db-1'
    $DbUser = 'erp_user'
    $AdminDb = 'erp_db'
    $TestDb = 'test_erp_db'
    $BaseDb = 'test_erp_db_base'   # WOW8-local : snapshot migre, clone par TEMPLATE
    $RunNamePattern = 'erp-agentique-django_core-run'

    function Invoke-Psql([string]$sql) {
        docker exec $DbContainer psql -U $DbUser -d $AdminDb -v ON_ERROR_STOP=1 -c $sql
        if ($LASTEXITCODE -ne 0) { throw "psql a echoue : $sql" }
    }
    function Test-DbExists([string]$name) {
        $r = docker exec $DbContainer psql -U $DbUser -d $AdminDb -tAc `
            "SELECT 1 FROM pg_database WHERE datname='$name'"
        return ($r -and $r.Trim() -eq '1')
    }
    function Remove-Db([string]$name) {
        Invoke-Psql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$name' AND pid<>pg_backend_pid();"
        Invoke-Psql "DROP DATABASE IF EXISTS $name;"
    }

    # ---- GARDE SINGLE-WRITER ----------------------------------------------
    Write-Host "-> Verification qu'aucun autre run de tests backend n'est actif..."
    $existing = docker ps --filter "name=$RunNamePattern" --format '{{.Names}}'
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Impossible d'interroger docker. Docker Desktop tourne-t-il ?"; exit 1
    }
    if ($existing -and $existing.Trim().Length -gt 0) {
        Write-Host "REFUS DE DEMARRER : un run de tests backend est deja actif : $existing" -ForegroundColor Red
        Write-Host "test_erp_db est single-writer. Attendez, ou : docker rm -f $existing" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  OK — aucun run concurrent detecte."

    # ---- GARDE .env ------------------------------------------------------
    # Un worktree cree par `git worktree add` n'a PAS de .env (il est gitignore),
    # or docker compose charge les creds DB via `env_file: ./.env`. Sans lui, le
    # conteneur django recoit des creds vides et se FIGE sur une connexion morte
    # - c'est la fausse "attente de 2h" qu'un run recent a prise pour un OOM/
    # deadlock. On auto-repare en copiant le .env d'un worktree voisin.
    $EnvFile = Join-Path $RepoRoot '.env'
    if (-not (Test-Path $EnvFile)) {
        Write-Host "-> .env absent dans ce worktree - recuperation depuis un worktree voisin..."
        $wtPaths = @()
        foreach ($ln in (git -C $RepoRoot worktree list --porcelain)) {
            if ($ln -like 'worktree *') { $wtPaths += ($ln.Substring(9).Trim() -replace '/', '\') }
        }
        $src = $wtPaths |
            Where-Object { $_ -ne $RepoRoot -and (Test-Path (Join-Path $_ '.env')) } |
            Select-Object -First 1
        if ($src) {
            Copy-Item (Join-Path $src '.env') $EnvFile
            Write-Host "  .env copie depuis $src (evite le hang creds-DB-vides du conteneur)." -ForegroundColor Green
        } else {
            Write-Host "REFUS DE DEMARRER : aucun .env ici ni dans un worktree voisin." -ForegroundColor Red
            Write-Host "Sans .env, docker compose passe des creds DB vides et le conteneur django se fige." -ForegroundColor Yellow
            Write-Host "Placez un .env valide a la racine de ce worktree, puis relancez." -ForegroundColor Yellow
            exit 1
        }
    }

    $KeepDbFlag = @('--keepdb')

    # ---- -RestoreDb : clone TEMPLATE (~secondes) au lieu du rebuild (~heures)
    if ($RestoreDb) {
        if (Test-DbExists $BaseDb) {
            Write-Host "-> WOW8-local : clone de $BaseDb -> $TestDb par TEMPLATE (quasi instantane)..."
            Remove-Db $TestDb
            Invoke-Psql "CREATE DATABASE $TestDb TEMPLATE $BaseDb;"
            Write-Host "  Clone pret — --keepdb n'appliquera que les migrations ajoutees depuis le snapshot."
        } else {
            Write-Host "  Pas de snapshot $BaseDb — build a froid cette fois (puis -Snapshot pour figer)." -ForegroundColor Yellow
            Remove-Db $TestDb
            $KeepDbFlag = @()
        }
    }
    elseif ($RebuildDb) {
        Write-Host "==============================================================" -ForegroundColor Yellow
        Write-Host " AVERTISSEMENT — REBUILD A FROID (~heures). Preferez -RestoreDb." -ForegroundColor Yellow
        Write-Host "==============================================================" -ForegroundColor Yellow
        Remove-Db $TestDb
        $KeepDbFlag = @()
    }

    # ---- Commande de test --------------------------------------------------
    # L'image n'installe que requirements.txt — on ajoute les deps de TEST
    # (factory_boy/freezegun/tblib) dans le conteneur jetable (idempotent).
    $ModulesList = $Modules -split '\s+' | Where-Object { $_ -ne '' }
    $DjangoCmd = (@('python', 'manage.py', 'test') + $ModulesList + $KeepDbFlag +
        @('--parallel', "$Parallel", '-v1')) -join ' '
    $testArgs = @(
        'compose', '-p', $ComposeProject, 'run', '--rm', '--no-deps',
        '-e', 'DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev',
        'django_core', 'sh', '-c', "pip install -q -r requirements-dev.txt && $DjangoCmd"
    )
    Write-Host ""
    Write-Host "-> docker $($testArgs -join ' ')"
    Write-Host ""
    & docker @testArgs
    $testExitCode = $LASTEXITCODE

    # ---- -Snapshot : fige la base migree comme TEMPLATE (seulement si vert) -
    if ($Snapshot -and $testExitCode -eq 0) {
        Write-Host ""
        Write-Host "-> -Snapshot : $TestDb -> $BaseDb (TEMPLATE de base pour -RestoreDb)..."
        Remove-Db $BaseDb
        Invoke-Psql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$TestDb' AND pid<>pg_backend_pid();"
        Invoke-Psql "CREATE DATABASE $BaseDb TEMPLATE $TestDb;"
        Write-Host "  Snapshot fige — les prochains -RestoreDb cloneront en secondes." -ForegroundColor Green
    }

    Write-Host ""
    if ($testExitCode -eq 0) {
        Write-Host "OK — Tests backend : SUCCES (modules: $Modules)" -ForegroundColor Green
    } else {
        Write-Host "ECHEC — Tests backend (code $testExitCode, modules: $Modules)" -ForegroundColor Red
    }
    exit $testExitCode
}
finally {
    Pop-Location
}
