# scripts/pile_locale.ps1 - AMET99 : monte (ou remet a jour) la PILE LOCALE d'un run.
#
# Utilise par les audits (METHODE B.0), acceptation.ps1, rejouer_parcours.py et
# scripts/setup-nightly-qa.ps1 (qui l'appelle - survivant unique de ces etapes).
# Chaque etape imprime son verdict ; un prerequis manquant est NOMME avec
# l'action a faire (jamais installe en silence) ; seed_demo n'est JAMAIS lance
# avec le drapeau de forcage.
#
# Usage :
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pile_locale.ps1
#   ... -Build    : docker compose up -d --build (tout, 1er montage ; plusieurs min)
#   ... -DryRun   : imprime les commandes sans rien executer
#
# Compatible Windows PowerShell 5.1 : ASCII seulement, pas de && / || / ?: / ??.

param(
    [switch]$Build,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Say([string]$Message) { Write-Host $Message }
function Fail([string]$Message) {
    Write-Host ('ECHEC : ' + $Message) -ForegroundColor Red
    exit 1
}

# Commandes natives : sous 'Stop', PS 5.1 transforme stderr en erreur fatale.
function Invoke-Native([scriptblock]$Block) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = @(& $Block 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    return [pscustomobject]@{ Code = $code; Lines = $lines }
}

function Invoke-Shown([string]$Label, [scriptblock]$Block) {
    Say ('> ' + $Label)
    if ($DryRun) { Say '  [dry-run] non execute.'; return 0 }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Block 2>&1 | ForEach-Object { Write-Host ('  ' + $_.ToString()) }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    return $code
}

function Get-HttpStatus([string]$Url) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
        return [int]$resp.StatusCode
    } catch {
        $r = $_.Exception.Response
        if ($null -ne $r) { return [int]$r.StatusCode }
        return 0
    }
}

# Sante : racine 200 ET API 401 (non authentifie = Django repond).
function Wait-Stack([int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $root = Get-HttpStatus 'http://localhost/'
        $api = Get-HttpStatus 'http://localhost/api/django/'
        if (($root -eq 200) -and ($api -eq 401)) { return $true }
        Start-Sleep -Seconds 10
    }
    return $false
}

Set-Location -LiteralPath $RepoRoot
Say ('pile locale - depot : ' + $RepoRoot)

# ---- 1. Docker Desktop ---------------------------------------------------------
if ($DryRun) {
    Say '> docker info [dry-run] non execute.'
} elseif ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    Say 'ACTION : Docker absent - installer Docker Desktop, le demarrer, puis relancer.'
    exit 1
} else {
    $di = Invoke-Native { docker info --format '{{.ServerVersion}}' }
    if ($di.Code -ne 0) {
        Say 'ACTION : Docker Desktop ne repond pas - le demarrer, puis relancer.'
        exit 1
    }
    Say ('OK - Docker Desktop ' + ($di.Lines -join ' ').Trim())
}

# ---- 2. .env + verrou single-writer des tests --------------------------------
$EnvFile = Join-Path $RepoRoot '.env'
if (-not (Test-Path -LiteralPath $EnvFile)) {
    if ($DryRun) { Say '> copie .env.example vers .env [dry-run] non execute.' } else {
        Copy-Item -LiteralPath (Join-Path $RepoRoot '.env.example') -Destination $EnvFile
        Say 'OK - .env cree depuis .env.example (OCR, chatbot, e-mail restent inactifs sans leurs cles).'
    }
}
if ((Test-Path -LiteralPath $EnvFile) -and (-not $DryRun)) {
    $debugLine = @(Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^\s*DJANGO_DEBUG\s*=' }) | Select-Object -Last 1
    if (($null -ne $debugLine) -and ($debugLine -notmatch '=\s*(True|true|1)\s*$')) {
        Say ('ACTION : ' + $debugLine.Trim() + ' dans .env - seed_demo exige DJANGO_DEBUG=True en LOCAL (jamais de forcage). Corriger puis relancer.')
        exit 1
    }
}
if (-not $DryRun) {
    $held = Invoke-Native { docker ps --filter 'name=erp-agentique-django_core-run' --format '{{.Names}}' }
    $heldNames = @($held.Lines | Where-Object { $_ -match 'erp-agentique-django_core-run' })
    if ($heldNames.Count -gt 0) {
        Say ('ACTION : un run de tests backend tient le verrou single-writer (' + ($heldNames -join ', ') + '). Attendre sa fin, puis relancer.')
        exit 1
    }
}
Say 'RAPPEL : un seul run de tests backend a la fois (verrou single-writer de scripts/test-backend.ps1, test_erp_db partage).'

# ---- 3. Stack, migrations, rebuild du front -----------------------------------
if ($Build) {
    $code = Invoke-Shown 'docker compose up -d --build (premier build : plusieurs minutes)' { docker compose up -d --build }
} else {
    $code = Invoke-Shown 'docker compose up -d' { docker compose up -d }
}
if ($code -ne 0) { Fail 'docker compose up.' }
$code = Invoke-Shown 'migrations' { docker compose exec -T django_core python manage.py migrate --noinput }
if ($code -ne 0) { Fail 'manage.py migrate.' }
if (-not $Build) {
    $code = Invoke-Shown 'rebuild du front (le build Vite est fige dans l''image)' { docker compose up -d --build frontend }
    if ($code -ne 0) { Fail 'docker compose up -d --build frontend.' }
}

# ---- 4. Societes demo (jamais de forcage) ------------------------------------------
$probe = "from authentication.models import Company; print('DEMO_STATE=' + ','.join(s + ':' + ('SEEDED' if Company.objects.filter(slug=s, produits__isnull=False).exists() else 'EMPTY') for s in ('taqinor-demo', 'taqinor-demo-full')))"
if ($DryRun) {
    Say '> sonde des societes demo ; seed_demo puis seed_demo_company si vides [dry-run] non execute.'
} else {
    $ds = Invoke-Native { docker compose exec -T django_core python manage.py shell -c $probe }
    $demo = ($ds.Lines -join ' ')
    if ($demo -notmatch 'DEMO_STATE=') { Fail ('etat des societes demo illisible : ' + $demo) }
    if ($demo -match 'taqinor-demo:EMPTY') {
        $code = Invoke-Shown 'seed_demo (societe demo vide)' { docker compose exec -T django_core python manage.py seed_demo }
        if ($code -ne 0) { Fail 'seed_demo a refuse (DJANGO_DEBUG=True requis dans le .env LOCAL ; jamais de forcage).' }
    } else { Say 'OK - societe taqinor-demo deja seedee.' }
    if ($demo -match 'taqinor-demo-full:EMPTY') {
        $code = Invoke-Shown 'seed_demo_company (societe demo riche vide)' { docker compose exec -T django_core python manage.py seed_demo_company }
        if ($code -ne 0) { Fail 'seed_demo_company a refuse.' }
    } else { Say 'OK - societe taqinor-demo-full deja seedee.' }
}

# ---- 5. Sante --------------------------------------------------------------------
if ($DryRun) {
    Say '> sante : http://localhost/ = 200 et /api/django/ = 401 [dry-run] non execute.'
    exit 0
}
Say 'attente de la stack : http://localhost/ = 200 et /api/django/ = 401 ...'
if (-not (Wait-Stack 600)) { Fail 'la stack ne repond pas comme attendu apres 10 min (docker compose ps / docker compose logs django_core).' }
Say 'OK - pile locale saine (racine 200, API 401).'
exit 0
