# scripts/preflight.ps1 — run EVERY fast CI gate locally, in the prod 3.11 image,
# in ONE pass, and report ALL failures at once. Run this BEFORE you push a batch.
#
# WHY (2026-07-11): a plan run pushed, watched `stage-names` go red, fixed one
# check, pushed again, watched it go red on a DIFFERENT check, ... — it burned
# FOUR CI round-trips (FE-SCA orphan prefix -> check_modules -> test-determinism
# -> flake8 -> lint-imports) on failures that are ALL locally checkable in
# seconds. It only ran 3 of the 11 stage-names sub-checks locally. This script
# runs them ALL so the first push is already green on the fast gates. It does NOT
# run the heavy backend-tests suite — that is the slow gate; use
# scripts/test-backend.ps1 for that. Fast gate here, full suite there.
#
# PARITE, PAS RECOPIE (18/08/2026, PR #536). La version precedente portait une
# COPIE MANUELLE des listes d'etapes des jobs `backend-lint` et `stage-names`, et
# ces copies avaient derive : preflight annoncait 16/16 vert pendant que la CI du
# meme push echouait sur `check_on_delete.py --financial` et sur
# `check_choices_declares.py` — deux checks dont preflight n'avait jamais entendu
# parler (il couvrait 3 des 23 checks de backend-lint et 12 des 29 de
# stage-names). Un preflight vert qui n'implique pas un gate vert est PIRE que pas
# de preflight : il achete un aller-retour CI avec une fausse confiance.
# Desormais preflight ne possede plus aucune liste : scripts/ci_fast_gate_steps.py
# lit .github/workflows/ci.yml — le meme fichier que GitHub — et rend les etapes
# des deux jobs, memes commandes, memes drapeaux, meme ordre. Ajouter un check
# dans ci.yml suffit : preflight le joue au run suivant, sans rien a resynchroniser.
#
# Faithful to CI: every check runs on the SAME Python 3.11 image CI uses (via the
# docker compose `django_core` service), over a repo-root bind mount, with the
# exact commands ci.yml runs. No host Python / flake8 needed. Never masks an exit
# code behind a pipe.
#
# Trois etapes de ci.yml sont volontairement sautees (voir _SKIPS dans
# ci_fast_gate_steps.py) : elles ne font que PREPARER le runner GitHub (apt-get
# des libs WeasyPrint, pip install -r requirements.txt, pip install flake8 +
# import-linter) et l'image prod les fournit deja. Le script echoue bruyamment si
# l'une de ces regles cesse de correspondre a une etape reelle : la garde
# anti-derive fonctionne dans les deux sens.

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
        # Pure-Python fast gates on host python: the WHOLE `stage-names` job, read
        # straight out of ci.yml (that job installs nothing in CI either — bare
        # setup-python + stdlib scripts — so the host can run it faithfully).
        # backend-lint is NOT runnable here: it needs the 3.11 image + its deps.
        Write-Host "-> Mode -NoDocker : job stage-names uniquement, sur python hote." -ForegroundColor Yellow
        $raw = & python scripts/ci_fast_gate_steps.py --format tsv stage-names
        if ($LASTEXITCODE -ne 0) {
            Write-Host "REFUS : impossible d'extraire les etapes de ci.yml (voir l'erreur ci-dessus)." -ForegroundColor Red
            exit 1
        }
        $checks = @()
        foreach ($ln in $raw) {
            if ([string]::IsNullOrWhiteSpace($ln)) { continue }
            $p = $ln -split "`t", 3
            $checks += , @($p[0], $p[1], $p[2])
        }
        Write-Host ("   $($checks.Count) etapes reprises telles quelles de ci.yml.") -ForegroundColor Yellow
        $fails = @()
        foreach ($c in $checks) {
            Write-Host ""; Write-Host "=== $($c[0]) ===" -ForegroundColor Cyan
            if ($c[1] -ne '.') { Push-Location $c[1] }
            try { Invoke-Expression $c[2] } finally { if ($c[1] -ne '.') { Pop-Location } }
            if ($LASTEXITCODE -ne 0) { $fails += $c[0]; Write-Host "FAIL: $($c[0])" -ForegroundColor Red }
            else { Write-Host "PASS: $($c[0])" -ForegroundColor Green }
        }
        Write-Host ""
        if ($fails.Count -gt 0) {
            Write-Host ("PREFLIGHT FAILED (" + $fails.Count + "): " + ($fails -join ', ')) -ForegroundColor Red
            exit 1
        }
        Write-Host "PREFLIGHT OK (stage-names complet, host python)." -ForegroundColor Green
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
# PARITE AUTOMATIQUE AVEC ci.yml (18/08/2026). Les listes de checks ne sont PLUS
# recopiees ici : scripts/ci_fast_gate_steps.py les lit dans .github/workflows/ci.yml
# et les rend pretes a executer, memes commandes et memes drapeaux. C'est le
# correctif de fond de l'incident PR #536, ou un preflight "16/16 vert" a laisse
# passer deux rouges CI (check_on_delete.py --financial cote backend-lint,
# check_choices_declares.py cote stage-names) que ses copies manuelles ignoraient.
# Ajouter une etape dans ci.yml suffit desormais : preflight la joue au run suivant.
run_job() {
  if ! python scripts/ci_fast_gate_steps.py "$1" > "/tmp/steps-$1.sh"; then
    echo "FAIL: extraction des etapes du job '$1' depuis ci.yml"
    fails="$fails extraction-$1"
    return 1
  fi
  echo ""
  echo "### job CI '$1' : $(grep -c '^step ' /tmp/steps-$1.sh) etapes reprises de ci.yml"
  . "/tmp/steps-$1.sh"
}

echo "-> installing flake8 + import-linter (CI backend-lint deps)..."
pip install -q flake8 import-linter==2.11

# `backend-lint` est devenu un agregateur mince (WOW-CI2) : ses controles
# reels vivent dans ces deux lanes. On suit le TRAVAIL, pas le nom du check.
run_job backend-lint-fast
run_job backend-openapi
# Pre-etape du job backend-tests-shard (derive modele<->migration, la classe de
# rouge CI n1). Elle n'appartient ni a backend-lint ni a stage-names, donc elle
# reste declaree explicitement ici.
step "makemigrations-check" "cd backend/django_core && python manage.py makemigrations --check --dry-run"
run_job stage-names

echo ""
if [ -n "$fails" ]; then
  echo "PREFLIGHT FAILED:$fails"
  exit 1
fi
echo "PREFLIGHT OK - all fast gates green (3.11-faithful, parite ci.yml)."
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
