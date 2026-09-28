# scripts/nightly-qa.ps1 - lanceur de la passe QA de nuit (QAH11).
#
# Execute chaque nuit par la tache planifiee Windows "TAQINOR nightly QA" (creee
# par scripts/setup-nightly-qa.ps1, voir docs/nightly-qa.md). Ordre, et pourquoi :
#   1. kill switch docs/qa-explorer.config.yml lu EN PREMIER (enabled: false ->
#      sortie propre, rien tire, rien construit, rien lance) ;
#   2. refus si une passe precedente tourne encore (verrou PID) ;
#   3. git pull de main (seulement si le checkout est sur main et propre - jamais
#      toucher au travail en cours d'un humain) ;
#   4. kill switch relu apres le pull + "skill pas encore cree" = sortie propre ;
#   5. stack docker debout (build), migrations, seed_demo si la societe demo est
#      vide (JAMAIS le drapeau de forcage) ;
#   6. refus si le verrou single-writer de scripts/test-backend.ps1 est tenu ;
#   7. claude -p headless sur l'abonnement Claude (aucune cle API), modele
#      explicite, liste d'outils autorises, chien de garde max_minutes + 30 ;
#   8. journal horodate dans logs/nightly-qa/ (ignore par git via logs/).
# Cible UNIQUE : la stack locale http://localhost. Jamais la prod. Ne touche
# jamais aux crons GitHub.
#
# Usage :
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\nightly-qa.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\nightly-qa.ps1 -Skill error-autopilot
#
# Codes de sortie :
#   0 = passe terminee, OU sortie propre voulue (kill switch off, skill absent)
#   1 = echec (git, docker, migrations, seed, claude en erreur, chien de garde)
#   2 = refus de demarrer (passe precedente en cours, verrou test-backend tenu,
#       checkout pas sur un main propre)
#
# Compatible Windows PowerShell 5.1 : ASCII seulement, pas de && / || / ?: / ??.

param(
    [ValidateSet('qa-explorer', 'error-autopilot')]
    [string]$Skill = 'qa-explorer'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

# ---- 1. KILL SWITCH - lu AVANT git, docker ou claude -------------------------
$ConfigRel = 'docs/qa-explorer.config.yml'
$script:MaxMinutes = 240
if ($Skill -eq 'error-autopilot') {
    $ConfigRel = 'docs/error-autopilot.config.yml'
    $script:MaxMinutes = 480
}
$ConfigPath = Join-Path $RepoRoot $ConfigRel
$SkillRel = '.claude/skills/' + $Skill + '/SKILL.md'
$SkillPath = Join-Path $RepoRoot $SkillRel

function Read-KillSwitch([string]$Path) {
    # State = 'true' | 'false' | 'missing' | 'unreadable' ; MaxMinutes si present.
    $state = 'missing'
    $minutes = 0
    if (Test-Path -LiteralPath $Path) {
        $state = 'unreadable'
        foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
            if ($line -match '^\s*enabled\s*:\s*(true|false)\s*(#.*)?$') { $state = $Matches[1] }
            if ($line -match '^\s*max_minutes\s*:\s*(\d+)') { $minutes = [int]$Matches[1] }
        }
    }
    return [pscustomobject]@{ State = $state; MaxMinutes = $minutes }
}

$KillSwitch = Read-KillSwitch $ConfigPath
if ($KillSwitch.MaxMinutes -gt 0) { $script:MaxMinutes = $KillSwitch.MaxMinutes }

# ---- Journal ------------------------------------------------------------------
$LogDir = Join-Path $RepoRoot 'logs\nightly-qa'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$LogFile = Join-Path $LogDir ($Skill + '-' + $Stamp + '.log')

function Write-Log([string]$Message) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

Write-Log ('nightly-qa : skill=' + $Skill + ' repo=' + $RepoRoot)
Write-Log ('kill switch ' + $ConfigRel + ' : ' + $KillSwitch.State)

if ($KillSwitch.State -eq 'false') {
    Write-Log 'DISABLED : enabled: false dans le kill switch - rien tire, rien construit, rien lance.'
    exit 0
}
if ($KillSwitch.State -eq 'unreadable') {
    Write-Log 'DISABLED : ligne "enabled: true|false" introuvable dans le kill switch - arret par securite.'
    exit 0
}
# 'missing' : le skill n'est peut-etre pas encore sur ce checkout ; on le
# re-verifie apres le git pull (etape 4), avant toute action docker ou claude.

# ---- 2. Une passe precedente tourne-t-elle encore ? ---------------------------
$LockFile = Join-Path $LogDir 'nightly-qa.lock'
if (Test-Path -LiteralPath $LockFile) {
    $oldPid = 0
    $raw = [string](Get-Content -LiteralPath $LockFile -Raw)
    $raw = $raw.Trim()
    $alive = $false
    if ([int]::TryParse($raw, [ref]$oldPid)) {
        $p = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($null -ne $p) {
            if ($p.ProcessName -match '^(powershell|pwsh)$') { $alive = $true }
        }
    }
    if ($alive) {
        Write-Log ('REFUS : une passe precedente tourne encore (PID ' + $oldPid + ', verrou ' + $LockFile + ').')
        exit 2
    }
    Write-Log ('Verrou perime (PID "' + $raw + '" absent) : supprime.')
    Remove-Item -LiteralPath $LockFile -Force
}
Set-Content -LiteralPath $LockFile -Value $PID -Encoding ASCII

# ---- Aides pour les commandes natives (PS 5.1 : jamais de 2>&1 sous 'Stop') ---
function Invoke-Step([string]$Label, [scriptblock]$Block) {
    Write-Log ('> ' + $Label)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = @(& $Block 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    foreach ($l in $lines) { Write-Log ('  ' + $l) }
    return [pscustomobject]@{ Code = $code; Lines = $lines }
}

function Test-DockerUp {
    if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    $r = Invoke-Step 'docker info (daemon joignable ?)' { docker info --format '{{.ServerVersion}}' }
    return ($r.Code -eq 0)
}

function Start-DockerDesktop {
    if (Test-DockerUp) { return $true }
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        Write-Log 'Docker Desktop introuvable a son emplacement par defaut.'
        return $false
    }
    Write-Log 'Demarrage de Docker Desktop...'
    Start-Process -FilePath $exe | Out-Null
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 15
        if (Test-DockerUp) { return $true }
    }
    return $false
}

function Get-TestBackendLock {
    # La garde single-writer de scripts/test-backend.ps1 : un conteneur
    # erp-agentique-django_core-run* actif = un run de tests backend en cours.
    $r = Invoke-Step 'verrou single-writer test-backend.ps1' { docker ps --filter 'name=erp-agentique-django_core-run' --format '{{.Names}}' }
    $names = @($r.Lines | Where-Object { $_ -match 'erp-agentique-django_core-run' })
    return ($names -join ', ')
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
    # Racine = 200 (frontend via nginx) ; API < 500 (405/401/400 = Django debout,
    # 502/503/504 = pas encore).
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $root = Get-HttpStatus 'http://localhost/'
        $api = Get-HttpStatus 'http://localhost/api/django/token/'
        if (($root -eq 200) -and ($api -gt 0) -and ($api -lt 500)) {
            Write-Log ('Stack debout : racine=' + $root + ' api=' + $api)
            return $true
        }
        Start-Sleep -Seconds 10
    }
    return $false
}

function Resolve-ClaudeExe {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $null }
    $path = $cmd.Source
    if ($path -match '\.ps1$') {
        # npm installe claude.ps1 ET claude.cmd : Start-Process ne lance que le second.
        $alt = [System.IO.Path]::ChangeExtension($path, '.cmd')
        if (Test-Path -LiteralPath $alt) { $path = $alt }
    }
    return $path
}

function Invoke-NightlyPass {
    Set-Location -LiteralPath $RepoRoot

    # ---- 3. Checkout : main propre, puis git pull ------------------------------
    $b = Invoke-Step 'branche courante' { git rev-parse --abbrev-ref HEAD }
    # stdout et stderr sont fusionnes : on ne garde que la ligne "nom de branche".
    $branch = [string](@($b.Lines | Where-Object { $_ -match '^[A-Za-z0-9._/-]+$' }) | Select-Object -Last 1)
    if (($b.Code -ne 0) -or ($branch -ne 'main')) {
        Write-Log ('REFUS : le checkout n''est pas sur main (branche : "' + $branch + '"). Action : git checkout main dans ' + $RepoRoot + ' (rien n''a ete touche).')
        return 2
    }
    $s = Invoke-Step 'modifications suivies en cours ?' { git status --porcelain --untracked-files=no }
    # Seules les lignes au format porcelain comptent (pas les avertissements CRLF).
    $mods = @($s.Lines | Where-Object { $_ -match '^[ MADRCUT]{2} \S' })
    if (($s.Code -ne 0) -or ($mods.Count -gt 0)) {
        Write-Log 'REFUS : le checkout main a des modifications en cours - on ne tire rien par-dessus le travail d''un humain.'
        return 2
    }
    $pull = Invoke-Step 'git pull de main' { git pull --ff-only origin main }
    if ($pull.Code -ne 0) {
        Write-Log 'ECHEC : git pull --ff-only origin main.'
        return 1
    }

    # ---- 4. Kill switch relu apres le pull + skill present ? -------------------
    $ks = Read-KillSwitch $ConfigPath
    if ($ks.MaxMinutes -gt 0) { $script:MaxMinutes = $ks.MaxMinutes }
    Write-Log ('kill switch apres pull : ' + $ks.State)
    if ($ks.State -eq 'missing') {
        Write-Log ('SKILL PAS ENCORE CREE : ' + $ConfigRel + ' absent - sortie propre, rien lance.')
        return 0
    }
    if ($ks.State -ne 'true') {
        Write-Log 'DISABLED : kill switch off (ou illisible) apres le pull - sortie propre.'
        return 0
    }
    if (-not (Test-Path -LiteralPath $SkillPath)) {
        Write-Log ('SKILL PAS ENCORE CREE : ' + $SkillRel + ' absent - sortie propre, rien lance.')
        return 0
    }

    # ---- 5. Stack docker debout, migrations, demo seedee -----------------------
    if (-not (Start-DockerDesktop)) {
        Write-Log 'ECHEC : Docker ne repond pas. Action : demarrer Docker Desktop (et l''activer au demarrage de Windows).'
        return 1
    }
    $held = Get-TestBackendLock
    if ($held) {
        Write-Log ('REFUS : verrou single-writer de test-backend.ps1 tenu (' + $held + ') - un run de tests est en cours.')
        return 2
    }
    $up = Invoke-Step 'docker compose up -d --build' { docker compose up -d --build }
    if ($up.Code -ne 0) {
        Write-Log 'ECHEC : docker compose up -d --build.'
        return 1
    }
    if (-not (Wait-Stack 600)) {
        Write-Log 'ECHEC : la stack locale ne repond pas sur http://localhost apres 10 min.'
        return 1
    }
    $mig = Invoke-Step 'migrations (ne jamais interrompre)' { docker compose exec -T django_core python manage.py migrate --noinput }
    if ($mig.Code -ne 0) {
        Write-Log 'ECHEC : manage.py migrate.'
        return 1
    }
    if ($Skill -eq 'qa-explorer') {
        $probe = "from authentication.models import Company; c = Company.objects.filter(slug='taqinor-demo').first(); print('DEMO_STATE=' + ('SEEDED' if c is not None and c.produits.exists() else 'EMPTY'))"
        $st = Invoke-Step 'societe demo seedee ?' { docker compose exec -T django_core python manage.py shell -c $probe }
        $state = ($st.Lines -join ' ')
        if ($state -match 'DEMO_STATE=EMPTY') {
            $seed = Invoke-Step 'seed_demo (societe demo vide)' { docker compose exec -T django_core python manage.py seed_demo }
            if ($seed.Code -ne 0) {
                Write-Log 'ECHEC : seed_demo a refuse (DJANGO_DEBUG doit valoir True dans le .env LOCAL). Jamais de forcage.'
                return 1
            }
        } elseif ($state -notmatch 'DEMO_STATE=SEEDED') {
            Write-Log 'ECHEC : impossible de lire l''etat de la societe demo.'
            return 1
        }
    }

    # ---- 6. Verrou test-backend relu juste avant claude ------------------------
    $held = Get-TestBackendLock
    if ($held) {
        Write-Log ('REFUS : verrou single-writer de test-backend.ps1 tenu (' + $held + ').')
        return 2
    }

    # ---- 7. claude -p headless (abonnement Claude, aucune cle API) -------------
    $claudeExe = Resolve-ClaudeExe
    if ($null -eq $claudeExe) {
        Write-Log 'ECHEC : claude introuvable dans le PATH. Action : installer Claude Code puis "claude auth login".'
        return 1
    }
    if (Test-Path Env:ANTHROPIC_API_KEY) {
        # Une cle API ferait facturer la passe a l'API : on force l'abonnement.
        Remove-Item Env:ANTHROPIC_API_KEY
        Write-Log 'ANTHROPIC_API_KEY retiree de l''environnement de la passe (abonnement Claude uniquement).'
    }
    $env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = [string]($script:MaxMinutes * 60 * 1000)

    $prompt = 'run the ' + $Skill + ' skill (' + $SkillRel + ')'
    # --permission-mode dontAsk : tout ce qui n'est pas dans cette liste est
    # REFUSE (personne ne repond aux demandes la nuit). Les sous-agents gardent
    # leurs tags de modele (le skill les impose) ; l'orchestrateur est opus.
    $allowed = @(
        'Read', 'Grep', 'Glob', 'Edit', 'Write', 'Agent', 'Skill', 'ToolSearch',
        'mcp__playwright', 'mcp__chrome-devtools',
        'Bash(git *)', 'Bash(gh *)', 'Bash(docker *)', 'Bash(python *)',
        'Bash(PYTHONIOENCODING=utf-8 python *)', 'Bash(curl *)',
        'Bash(powershell *)', 'Bash(npm *)', 'Bash(npx *)', 'Bash(node *)',
        'Bash(flake8 *)', 'Bash(mkdir *)', 'Bash(cp *)',
        'Bash(rm -f logs/nightly-qa/*)', 'Bash(rm -f docs/qa-explorer/captures/*)'
    ) -join ','
    $argLine = '-p "' + $prompt + '" --model opus --output-format json --permission-mode dontAsk --allowedTools "' + $allowed + '"'
    $outFile = Join-Path $LogDir ($Skill + '-' + $Stamp + '.json')
    $errFile = Join-Path $LogDir ($Skill + '-' + $Stamp + '.stderr.txt')
    $timeoutMs = ($script:MaxMinutes + 30) * 60 * 1000
    Write-Log ('> claude ' + $argLine)
    Write-Log ('  chien de garde : ' + ($script:MaxMinutes + 30) + ' min ; sortie JSON : ' + $outFile)
    $proc = Start-Process -FilePath $claudeExe -ArgumentList $argLine -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile -NoNewWindow -PassThru
    $null = $proc.Handle   # PS 5.1 : sans cet acces, ExitCode reste vide
    if (-not $proc.WaitForExit($timeoutMs)) {
        Write-Log 'ECHEC : chien de garde depasse - arret de l''arbre de processus claude.'
        $kill = Invoke-Step 'taskkill /T /F' { taskkill /T /F /PID $proc.Id }
        $marker = Join-Path $LogDir 'qa-explorer.running'
        if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker -Force }
        return 1
    }
    $proc.WaitForExit()
    $claudeCode = $proc.ExitCode
    Write-Log ('claude termine : code ' + $claudeCode)

    $isError = $false
    if (Test-Path -LiteralPath $outFile) {
        $json = Get-Content -LiteralPath $outFile -Raw -Encoding UTF8
        try {
            $res = $json | ConvertFrom-Json
            if ($res.is_error) { $isError = $true }
            Write-Log ('cout estime (total_cost_usd) : ' + $res.total_cost_usd)
            foreach ($l in ([string]$res.result -split "`n")) {
                if ($l -match '^(QA_EXPLORER|ERROR_AUTOPILOT|ERROR_PLAN_STATUS|WEB_ERROR_STATUS)') { Write-Log ('  ' + $l.Trim()) }
            }
        } catch {
            Write-Log 'Sortie claude non-JSON (voir le fichier .json brut).'
        }
    }
    if (($claudeCode -ne 0) -or $isError) {
        Write-Log 'ECHEC : la passe claude a echoue (voir .json / .stderr.txt).'
        return 1
    }
    Write-Log 'Passe terminee.'
    return 0
}

$ExitCode = 1
try {
    $out = @(Invoke-NightlyPass)
    if ($out.Count -gt 0) { $ExitCode = [int]$out[-1] }
} catch {
    Write-Log ('ECHEC inattendu : ' + $_.Exception.Message)
    $ExitCode = 1
} finally {
    Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
    Write-Log ('fin : code de sortie ' + $ExitCode)
}
exit $ExitCode
