# scripts/preflight.ps1 — run EVERY fast CI gate locally, in the prod 3.11 image,
# in ONE pass, and report ALL failures at once. Run this BEFORE you push a batch.
#
# WHY (2026-07-11): a plan run pushed, watched `stage-names` go red, fixed one
# check, pushed again, watched it go red on a DIFFERENT check, ... — it burned
# FOUR CI round-trips (FE-SCA orphan prefix -> check_modules -> test-determinism
# -> flake8 -> lint-imports) on failures that are ALL locally checkable in
# seconds. It only ran 3 of the 11 stage-names sub-checks locally. This script
# runs them ALL (plus backend-lint's compileall/flake8/lint-imports and the
# makemigrations drift check) so the first push is already green on the fast
# gates. It does NOT run the heavy backend-tests suite — that is the slow gate;
# use scripts/test-backend.ps1 for that. Fast gate here, full suite there.
#
# Faithful to CI: every check runs on the SAME Python 3.11 image CI uses (via the
# docker compose `django_core` service), over a repo-root bind mount, with the
# exact commands ci.yml runs. No host Python / flake8 needed. Never masks an exit
# code behind a pipe.

param(
    [switch]$NoDocker   # skip the container checks (compileall/flake8/lint-imports/
                        # makemigrations); run only the pure-Python stage-names checks
                        # on host `python`. A fallback when docker is down.
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    $ComposeProject = 'erp-agentique'

    # ---- GARDE .env (worktree cree par `git worktree add` n'a pas de .env) -----
    # Meme raison que test-backend.ps1 : compose charge les creds via env_file.
    if (-not $NoDocker) {
        $EnvFile = Join-Path $RepoRoot '.env'
        if (-not (Test-Path $EnvFile)) {
            $wtPaths = @()
            foreach ($ln in (git -C $RepoRoot worktree list --porcelain)) {
                if ($ln -like 'worktree *') { $wtPaths += ($ln.Substring(9).Trim() -replace '/', '\') }
            }
            $src = $wtPaths |
                Where-Object { $_ -ne $RepoRoot -and (Test-Path (Join-Path $_ '.env')) } |
                Select-Object -First 1
            if ($src) {
                Copy-Item (Join-Path $src '.env') $EnvFile
                Write-Host "  .env copie depuis $src (necessaire pour docker compose)." -ForegroundColor Green
            } else {
                Write-Host "REFUS : aucun .env ici ni dans un worktree voisin (necessaire pour compose)." -ForegroundColor Red
                Write-Host "Placez un .env valide, ou relancez avec -NoDocker (stage-names uniquement)." -ForegroundColor Yellow
                exit 1
            }
        }
    }

    if ($NoDocker) {
        # Pure-Python fast gates on host python (the 10 stage-names checks only;
        # compileall/flake8/lint-imports need the 3.11 image + deps).
        Write-Host "-> Mode -NoDocker : stage-names uniquement, sur python hote." -ForegroundColor Yellow
        $checks = @(
            @('check_stages',              'python scripts/check_stages.py'),
            @('check_modules',             'python scripts/check_modules.py'),
            @('check_test_determinism',    'python scripts/check_test_determinism.py'),
            @('check_test_tags',           'python scripts/check_test_tags.py'),
            @('check_invariants',          'python scripts/check_invariants.py'),
            @('codemap_fingerprint',       'python scripts/codemap_fingerprint.py --check'),
            @('check_safe_migrations',     'python scripts/check_safe_migrations.py'),
            @('test_check_safe_migrations','python -m unittest scripts.tests.test_check_safe_migrations'),
            @('check_build_order',         'python scripts/check_build_order.py'),
            @('test_check_build_order',    'python -m unittest scripts.tests.test_check_build_order')
        )
        $fails = @()
        foreach ($c in $checks) {
            Write-Host ""; Write-Host "=== $($c[0]) ===" -ForegroundColor Cyan
            Invoke-Expression $c[1]
            if ($LASTEXITCODE -ne 0) { $fails += $c[0]; Write-Host "FAIL: $($c[0])" -ForegroundColor Red }
            else { Write-Host "PASS: $($c[0])" -ForegroundColor Green }
        }
        Write-Host ""
        if ($fails.Count -gt 0) {
            Write-Host ("PREFLIGHT FAILED (" + $fails.Count + "): " + ($fails -join ', ')) -ForegroundColor Red
            exit 1
        }
        Write-Host "PREFLIGHT OK (stage-names, host python)." -ForegroundColor Green
        exit 0
    }

    # ---- Full preflight in the prod 3.11 image, one container, all checks ------
    # Repo root bind-mounted at /repo so root-level scripts (scripts/check_*.py,
    # compileall over backend/fastapi_ia) AND backend/django_core-level checks
    # (lint-imports, makemigrations) all run exactly as ci.yml runs them. Each
    # check runs regardless of earlier failures, so ONE pass surfaces EVERY issue.
    $inner = @'
set +e
cd /repo
fails=""
step() {
  echo ""
  echo "=== $1 ==="
  # Subshell so a check's `cd` (e.g. into backend/django_core) never leaks into
  # the next check's working directory.
  ( eval "$2" )
  if [ $? -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fails="$fails $1"; fi
}
echo "-> installing flake8 + import-linter (CI backend-lint deps)..."
pip install -q flake8 import-linter==2.11

# backend-lint parity
step "compileall-3.11" "python -m compileall -q -j 0 backend/django_core/apps backend/django_core/erp_agentique backend/fastapi_ia"
step "flake8"          "flake8 backend --max-line-length=120 --extend-ignore=E501 --exclude=migrations"
step "lint-imports"    "cd backend/django_core && lint-imports"
# backend-tests-shard pre-step: model<->migration drift (the #1 CI-red class)
step "makemigrations-check" "cd backend/django_core && python manage.py makemigrations --check --dry-run"
# stage-names parity (all 10)
step "check_stages"              "python scripts/check_stages.py"
step "check_modules"             "python scripts/check_modules.py"
step "check_test_determinism"    "python scripts/check_test_determinism.py"
step "check_test_tags"           "python scripts/check_test_tags.py"
step "check_invariants"          "python scripts/check_invariants.py"
step "codemap_fingerprint"       "python scripts/codemap_fingerprint.py --check"
step "check_safe_migrations"     "python scripts/check_safe_migrations.py"
step "test_check_safe_migrations" "python -m unittest scripts.tests.test_check_safe_migrations"
step "check_build_order"         "python scripts/check_build_order.py"
step "test_check_build_order"    "python -m unittest scripts.tests.test_check_build_order"

echo ""
if [ -n "$fails" ]; then
  echo "PREFLIGHT FAILED:$fails"
  exit 1
fi
echo "PREFLIGHT OK - all fast gates green (3.11-faithful)."
'@
    # Normalise to LF, then base64-encode. Windows PowerShell 5.1 mangles embedded
    # double-quotes/newlines when passing a multi-line arg to a native exe (docker),
    # which corrupts the sh script ("Unterminated quoted string"). Base64 has no
    # quotes/newlines, so it survives the CLI boundary intact; the container decodes
    # and runs it.
    $inner = $inner -replace "`r`n", "`n"
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($inner))

    # Docker Desktop parses the -v bind mount more reliably with forward slashes
    # (the drive-letter colon vs. the source:target colon is otherwise ambiguous).
    $RepoFwd = $RepoRoot -replace '\\', '/'
    $composeArgs = @(
        'compose', '-p', $ComposeProject, 'run', '--rm', '--no-deps',
        '-v', "${RepoFwd}:/repo",
        '-e', 'DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev',
        'django_core', 'sh', '-c', "echo $b64 | base64 -d | sh"
    )
    Write-Host "-> Preflight : tous les gates rapides dans l'image 3.11 (une passe)..." -ForegroundColor Cyan
    & docker @composeArgs
    $code = $LASTEXITCODE
    Write-Host ""
    if ($code -eq 0) {
        Write-Host "OK — preflight vert : poussez, la CI passera les gates rapides." -ForegroundColor Green
    } else {
        Write-Host "ECHEC — corrigez les checks FAIL ci-dessus AVANT de pousser (evite un cycle CI rouge)." -ForegroundColor Red
    }
    exit $code
}
finally {
    Pop-Location
}
