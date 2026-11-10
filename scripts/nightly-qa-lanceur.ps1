# scripts/nightly-qa-lanceur.ps1 - lanceur de la QA de nuit installe HORS du depot (ADCG15).
#
# setup-nightly-qa.ps1 le COPIE dans %LOCALAPPDATA%\taqinor\ et l'enregistre comme action
# des taches "TAQINOR nightly QA" / "TAQINOR error-autopilot" : un scripts\nightly-qa.ps1
# absent du checkout laisse une trace lisible au lieu d'un 0xFFFD0000 muet.
# Aucune reparation automatique du checkout. Codes : celui de nightly-qa.ps1, 3 = script absent.
# Compatible Windows PowerShell 5.1 : ASCII seulement, pas de && / || / ?: / ??.

param(
    [Parameter(Mandatory = $true)][string]$Depot,
    [string]$Skill = 'qa-explorer'
)

$ErrorActionPreference = 'Continue'
$Journal = Join-Path (Join-Path $env:LOCALAPPDATA 'taqinor') 'nightly-qa.log'

function Trace([string]$Message) {
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Journal) | Out-Null
        Add-Content -LiteralPath $Journal -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Message) -Encoding UTF8
    } catch { }
}

Trace ('lancement skill ' + $Skill + ' depot ' + $Depot + ' PID ' + $PID)
$Script = Join-Path (Join-Path $Depot 'scripts') 'nightly-qa.ps1'
if (-not (Test-Path -LiteralPath $Script)) {
    $etat = 'git indisponible'
    try { $etat = ((@(& git -C $Depot status --porcelain -- scripts 2>&1 | ForEach-Object { $_.ToString() })) -join ' | ').Trim() } catch { }
    if ($etat -eq '') { $etat = 'propre' }
    Trace ('ECHEC lancement : scripts\nightly-qa.ps1 absent de ' + $Depot + ' (git status : ' + $etat + ')')
    exit 3
}
$code = 1
try {
    & $Script -Skill $Skill
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
} catch {
    Trace ('exception : ' + $_.Exception.Message)
}
Trace ('fin code ' + $code)
exit $code
