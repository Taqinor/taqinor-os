# scripts/setup-nightly-qa.ps1 - commande "setup nightly QA" (QAH11).
#
# Configure LA MACHINE OU ON LA TAPE comme machine de QA de nuit - rien d'autre :
# aucun drain de plan, aucun merge, aucun deploy. Idempotent : la relancer met
# la tache a jour (schtasks /Create ... /F = creer OU remplacer), jamais de
# doublon. Ne touche jamais aux crons GitHub (release-verify 03:00 UTC, mutation
# 03:30 UTC tournent sur les runners GitHub, pas sur cette machine).
#
# Etapes :
#   1. prerequis : git, Node >= 20 (20.19+ pour chrome-devtools-mcp), Docker
#      Desktop demarre, Claude Code installe ET connecte, Google Chrome - chaque
#      manque = une ligne d'action claire, JAMAIS d'installation silencieuse ;
#   2. depot sur main, propre, a jour (git pull --ff-only) ;
#   3. .env cree depuis .env.example s'il manque ;
#   4. docker compose up -d --build, attente de la stack, migrations ;
#   5. seed_demo si la societe demo est vide (JAMAIS le drapeau de forcage) ;
#   6. rappel : approuver Playwright MCP + Chrome DevTools MCP dans /mcp ;
#   7. tache planifiee Windows "TAQINOR nightly QA" (quotidienne, heure LOCALE,
#      23:00 par defaut) qui lance scripts/nightly-qa.ps1 ; option
#      -WithErrorAutopilot : tache "TAQINOR error-autopilot" (12:00 par defaut).
#
# Usage :
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-nightly-qa.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-nightly-qa.ps1 -Time 01:30
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-nightly-qa.ps1 -WithErrorAutopilot
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-nightly-qa.ps1 -WithErrorAutopilot -ErrorAutopilotTime 13:00
#
# Compatible Windows PowerShell 5.1 : ASCII seulement, pas de && / || / ?: / ??.

param(
    [string]$Time = '23:00',
    [switch]$WithErrorAutopilot,
    [string]$ErrorAutopilotTime = '12:00'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot 'scripts\nightly-qa.ps1'
$TaskQa = 'TAQINOR nightly QA'
$TaskAutopilot = 'TAQINOR error-autopilot'

function Say([string]$Message) { Write-Host $Message }
function Fail([string]$Message) {
    Write-Host ('ECHEC : ' + $Message) -ForegroundColor Red
    exit 1
}

function ConvertTo-HHMM([string]$Value, [string]$Name) {
    if ($Value -notmatch '^(\d{1,2}):(\d{2})$') { Fail ($Name + ' doit etre au format HH:MM (ex. 23:00), recu "' + $Value + '".') }
    $h = [int]$Matches[1]
    $m = [int]$Matches[2]
    if (($h -gt 23) -or ($m -gt 59)) { Fail ($Name + ' hors bornes : "' + $Value + '".') }
    return ('{0:D2}:{1:D2}' -f $h, $m)
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

function Test-ChromeInstalled {
    $keys = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'
    )
    foreach ($k in $keys) { if (Test-Path -LiteralPath $k) { return $true } }
    $paths = @(
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
    )
    if (${env:ProgramFiles(x86)}) { $paths += (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe') }
    foreach ($p in $paths) { if (Test-Path -LiteralPath $p) { return $true } }
    return $false
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

function Wait-Stack([int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $root = Get-HttpStatus 'http://localhost/'
        $api = Get-HttpStatus 'http://localhost/api/django/token/'
        if (($root -eq 200) -and ($api -gt 0) -and ($api -lt 500)) { return $true }
        Start-Sleep -Seconds 10
    }
    return $false
}

function Get-TaskCommand([string]$ScriptPath, [string]$ExtraArgs) {
    # Chemin sans espace : aucun guillemet (fonctionne partout). Avec espaces :
    # PS 5.1 (passage d'arguments "Legacy") exige des guillemets echappes \" pour
    # que schtasks recoive "..." ; PS 7.3+ les echappe lui-meme.
    $quoted = $ScriptPath
    if ($ScriptPath -match '\s') {
        $legacy = $true
        $v = Get-Variable -Name PSNativeCommandArgumentPassing -ErrorAction SilentlyContinue
        if ($null -ne $v) { if ([string]$v.Value -ne 'Legacy') { $legacy = $false } }
        if ($legacy) { $quoted = '\"' + $ScriptPath + '\"' } else { $quoted = '"' + $ScriptPath + '"' }
    }
    return ('powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ' + $quoted + $ExtraArgs)
}

function Register-DailyTask([string]$Name, [string]$At, [string]$ExtraArgs) {
    $tr = Get-TaskCommand $Runner $ExtraArgs
    if ($tr.Length -gt 261) { Fail ('commande de tache trop longue pour schtasks (' + $tr.Length + ' > 261) : deplacer le depot vers un chemin plus court.') }
    # /F = creer OU remplacer la tache du meme nom : relancer = mise a jour, jamais de doublon.
    $code = Invoke-Shown ('schtasks /Create /TN "' + $Name + '" /SC DAILY /ST ' + $At + ' /F') { schtasks /Create /TN $Name /TR $tr /SC DAILY /ST $At /F }
    if ($code -ne 0) { Fail ('schtasks /Create a echoue pour "' + $Name + '".') }
    $q = Invoke-Native { schtasks /Query /TN $Name /FO LIST }
    if ($q.Code -ne 0) { Fail ('tache "' + $Name + '" introuvable apres creation.') }
    # schtasks cree la tache avec "demarrer seulement sur secteur" : sur un portable
    # sur batterie a l'heure dite, elle ne partirait pas. Reglage best-effort.
    try {
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
        Set-ScheduledTask -TaskName $Name -Settings $settings | Out-Null
        Say '  reglage : demarre aussi sur batterie ; jamais deux instances a la fois.'
    } catch {
        Say ('  NOTE : reglage batterie non applique (' + $_.Exception.Message + ') - sur un portable, laisser le secteur branche la nuit.')
    }
    Say ('  OK - tache "' + $Name + '" : tous les jours a ' + $At + ' (heure locale de cette machine).')
}

$Time = ConvertTo-HHMM $Time '-Time'
$ErrorAutopilotTime = ConvertTo-HHMM $ErrorAutopilotTime '-ErrorAutopilotTime'
Set-Location -LiteralPath $RepoRoot
Say ('setup nightly QA - depot : ' + $RepoRoot)
Say ('heure de la passe : ' + $Time + ' (heure LOCALE ; 23:00 recommande - la journee, la passe partage la fenetre d''usage Claude, le CPU/RAM et le verrou du test DB avec vos sessions)')

# ---- 1. Prerequis (aucune installation silencieuse) --------------------------
$Actions = New-Object System.Collections.Generic.List[string]
$Verified = New-Object System.Collections.Generic.List[string]

if ($null -eq (Get-Command git -ErrorAction SilentlyContinue)) {
    $Actions.Add('git absent : installer Git for Windows (git-scm.com), puis rouvrir PowerShell.')
} else { $Verified.Add('git') }

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $nodeCmd) {
    $Actions.Add('Node.js absent : installer Node.js LTS >= 20.19 (nodejs.org), puis rouvrir PowerShell.')
} else {
    $nv = Invoke-Native { node --version }
    $nodeOk = $false
    $nodeText = ($nv.Lines -join ' ').Trim()
    if ($nodeText -match 'v(\d+)\.(\d+)') {
        $maj = [int]$Matches[1]
        $min = [int]$Matches[2]
        if (($maj -gt 20) -or (($maj -eq 20) -and ($min -ge 19))) { $nodeOk = $true }
    }
    if ($nodeOk) { $Verified.Add('Node ' + $nodeText) } else { $Actions.Add('Node.js trop ancien (' + $nodeText + ') : installer Node.js LTS >= 20.19 (exige par chrome-devtools-mcp).') }
}

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($null -eq $dockerCmd) {
    $Actions.Add('Docker absent : installer Docker Desktop, le demarrer, puis relancer cette commande.')
} else {
    $di = Invoke-Native { docker info --format '{{.ServerVersion}}' }
    if ($di.Code -ne 0) {
        $Actions.Add('Docker Desktop ne repond pas : le demarrer (et cocher "Start Docker Desktop when you sign in"), puis relancer cette commande.')
    } else {
        $dc = Invoke-Native { docker compose version }
        if ($dc.Code -ne 0) { $Actions.Add('docker compose (v2) indisponible : mettre Docker Desktop a jour.') } else { $Verified.Add('Docker Desktop') }
    }
}

$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if ($null -eq $claudeCmd) {
    $Actions.Add('Claude Code absent : l''installer (installeur officiel), puis "claude auth login" avec l''abonnement Claude.')
} else {
    $ca = Invoke-Native { claude auth status }
    if ($ca.Code -ne 0) {
        $Actions.Add('Claude Code n''est pas connecte : lancer "claude auth login" (abonnement Claude - pas de cle API).')
    } else { $Verified.Add('Claude Code connecte') }
}

if (-not (Test-ChromeInstalled)) {
    $Actions.Add('Google Chrome absent : l''installer (Playwright MCP et Chrome DevTools MCP pilotent Chrome).')
} else { $Verified.Add('Google Chrome') }

if ($Actions.Count -gt 0) {
    Say ''
    Say 'PREREQUIS MANQUANTS - rien n''a ete configure. A faire, puis relancer la commande :'
    foreach ($a in $Actions) { Say ('  - ' + $a) }
    exit 1
}
Say ('prerequis OK : ' + ($Verified -join ', '))

# ---- 2. Depot sur main, propre, a jour ---------------------------------------
$br = Invoke-Native { git rev-parse --abbrev-ref HEAD }
$branch = [string](@($br.Lines | Where-Object { $_ -match '^[A-Za-z0-9._/-]+$' }) | Select-Object -Last 1)
if ($branch -ne 'main') {
    Say ('ACTION : ce depot est sur la branche "' + $branch + '". Passer sur main (git checkout main) puis relancer - la commande ne change jamais de branche a votre place.')
    exit 1
}
$st = Invoke-Native { git status --porcelain --untracked-files=no }
$mods = @($st.Lines | Where-Object { $_ -match '^[ MADRCUT]{2} \S' })
if ($mods.Count -gt 0) {
    Say 'ACTION : main a des modifications en cours (git status). Les committer ou les mettre de cote, puis relancer.'
    exit 1
}
$code = Invoke-Shown 'git pull --ff-only origin main' { git pull --ff-only origin main }
if ($code -ne 0) { Fail 'git pull --ff-only origin main (main local diverge d''origin ?).' }

# ---- 3. .env ------------------------------------------------------------------
$EnvFile = Join-Path $RepoRoot '.env'
$Created = New-Object System.Collections.Generic.List[string]
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot '.env.example') -Destination $EnvFile
    $Created.Add('.env (copie de .env.example)')
    Say '.env cree depuis .env.example (les fonctions a cle - OCR, chatbot, e-mail - restent inactives sans leurs cles).'
}
$debugLine = @(Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^\s*DJANGO_DEBUG\s*=' }) | Select-Object -Last 1
if (($null -ne $debugLine) -and ($debugLine -notmatch '=\s*(True|true|1)\s*$')) {
    Say ('ACTION : ' + $debugLine.Trim() + ' dans .env - seed_demo exige DJANGO_DEBUG=True sur la stack LOCALE (jamais de forcage). Corriger puis relancer.')
    exit 1
}

# ---- 4. Stack docker ----------------------------------------------------------
$held = Invoke-Native { docker ps --filter 'name=erp-agentique-django_core-run' --format '{{.Names}}' }
$heldNames = @($held.Lines | Where-Object { $_ -match 'erp-agentique-django_core-run' })
if ($heldNames.Count -gt 0) {
    Say ('ACTION : un run de tests backend tient le verrou single-writer (' + ($heldNames -join ', ') + '). Attendre sa fin, puis relancer.')
    exit 1
}
$code = Invoke-Shown 'docker compose up -d --build (premier build : plusieurs minutes)' { docker compose up -d --build }
if ($code -ne 0) { Fail 'docker compose up -d --build.' }
Say 'attente de la stack sur http://localhost ...'
if (-not (Wait-Stack 600)) { Fail 'la stack locale ne repond pas sur http://localhost apres 10 min (docker compose ps / docker compose logs django_core).' }
$code = Invoke-Shown 'migrations' { docker compose exec -T django_core python manage.py migrate --noinput }
if ($code -ne 0) { Fail 'manage.py migrate.' }

# ---- 5. Societe demo ----------------------------------------------------------
$probe = "from authentication.models import Company; c = Company.objects.filter(slug='taqinor-demo').first(); print('DEMO_STATE=' + ('SEEDED' if c is not None and c.produits.exists() else 'EMPTY'))"
$ds = Invoke-Native { docker compose exec -T django_core python manage.py shell -c $probe }
$demo = ($ds.Lines -join ' ')
if ($demo -match 'DEMO_STATE=EMPTY') {
    $code = Invoke-Shown 'seed_demo (societe demo vide)' { docker compose exec -T django_core python manage.py seed_demo }
    if ($code -ne 0) { Fail 'seed_demo a refuse (DJANGO_DEBUG=True requis dans le .env LOCAL ; jamais de forcage).' }
    $Created.Add('societe demo (seed_demo)')
} elseif ($demo -match 'DEMO_STATE=SEEDED') {
    Say 'societe demo deja seedee - rien a faire.'
} else {
    Fail ('etat de la societe demo illisible : ' + $demo)
}

# ---- Kill switch (information) ------------------------------------------------
$cfg = Join-Path $RepoRoot 'docs\qa-explorer.config.yml'
if (Test-Path -LiteralPath $cfg) {
    $en = @(Get-Content -LiteralPath $cfg -Encoding UTF8 | Where-Object { $_ -match '^\s*enabled\s*:' }) | Select-Object -First 1
    if (($null -ne $en) -and ($en -match 'false')) { Say 'NOTE : docs/qa-explorer.config.yml a enabled: false - la tache sera creee mais chaque passe sortira sans rien faire.' }
} else {
    Say 'NOTE : le skill qa-explorer n''est pas encore sur ce main - la tache sera creee et sortira proprement jusqu''a son arrivee.'
}

# ---- 6. Rappel MCP --------------------------------------------------------------
Say ''
Say 'RAPPEL /mcp (une fois par machine) : ouvrir "claude" a la racine du depot, taper /mcp, approuver'
Say '  "playwright" (Playwright MCP) et "chrome-devtools" (Chrome DevTools MCP) declares dans .mcp.json.'
Say '  La nuit, "claude -p" les charge sans demander ; l''approbation sert aux passes lancees a la main.'

# ---- 7. Taches planifiees ------------------------------------------------------
Say ''
Register-DailyTask $TaskQa $Time ''
$Created.Add('tache "' + $TaskQa + '" a ' + $Time)
if ($WithErrorAutopilot) {
    Register-DailyTask $TaskAutopilot $ErrorAutopilotTime ' -Skill error-autopilot'
    $Created.Add('tache "' + $TaskAutopilot + '" a ' + $ErrorAutopilotTime)
}

Say ''
Say ('VERIFIE : ' + ($Verified -join ', ') + ' ; depot sur main a jour ; stack locale debout (http://localhost) ; migrations appliquees.')
Say ('CREE / MIS A JOUR : ' + ($Created -join ' ; ') + '.')
Say 'ENCORE MANUEL : approuver les 2 serveurs MCP dans /mcp ; laisser le PC allume et la session ouverte a l''heure de la passe (veille = pas de passe).'
Say ('VERIFIER : schtasks /Query /TN "' + $TaskQa + '" /V /FO LIST (Last Run Time / Last Result) ; journaux dans logs\nightly-qa\.')
Say ('COUPER : schtasks /Change /TN "' + $TaskQa + '" /DISABLE, ou enabled: false dans docs/qa-explorer.config.yml. Voir docs/nightly-qa.md.')
exit 0
