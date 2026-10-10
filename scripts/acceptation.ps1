# scripts/acceptation.ps1 - AMET90 : joue l'ACCEPTATION EN DIRECT d'un groupe d'audit
# (CLAUDE.md etape 3-bis, METHODE C.4) et commite son enregistrement.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\acceptation.ps1 ADEP
#   ... -Build                         : pile_locale.ps1 -Build (premier montage)
#   ... -EtapesSupplementaires <json>  : fusionne des etapes jouees hors spec (P1-P4)
#   ... -DryRun                        : imprime les commandes sans rien executer
#
# 1) pile locale (scripts/pile_locale.ps1 : up, migrate, rebuild du front, seed_demo
#    si vide, sante) ; 2) spec frontend/e2e/acceptation/<g>.spec.js (projet Playwright
# `acceptation`, E2E_ACCEPTATION=1, http://localhost) qui ecrit l'enregistrement
# docs/audits/acceptation/<G>/<date>-<sha9>.md + .results.json ; 3) garde
# scripts/check_acceptation.py ; 4) commit de l'enregistrement et de ses captures
# SEULEMENT si la spec ET la garde sont vertes. Jamais de push.
# Windows PowerShell 5.1 : ASCII seulement, pas de && / || / ?: / ??.

param(
    [Parameter(Mandatory = $true)][string]$Groupe,
    [switch]$Build,
    [string]$EtapesSupplementaires = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Groupe = $Groupe.ToUpper()
$Spec = 'e2e/acceptation/' + $Groupe.ToLower() + '.spec.js'
$Date = Get-Date -Format 'yyyy-MM-dd'

function Run([string]$Label, [scriptblock]$Block) {
    Write-Host ('> ' + $Label)
    if ($DryRun) { Write-Host '  [dry-run] non execute.'; return 0 }
    & $Block 2>&1 | ForEach-Object { Write-Host ('  ' + $_.ToString()) }
    return $LASTEXITCODE
}

Set-Location -LiteralPath $RepoRoot
if (-not (Test-Path -LiteralPath (Join-Path 'frontend' $Spec))) {
    Write-Host ('ECHEC : spec absente frontend/' + $Spec + ' (format : frontend/e2e/acceptation/_format.md).')
    exit 1
}

$pile = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'pile_locale.ps1'))
if ($Build) { $pile += '-Build' }
if ($DryRun) { $pile += '-DryRun' }
& powershell @pile
if ($LASTEXITCODE -ne 0) { Write-Host 'ECHEC : pile locale (voir ci-dessus).'; exit 1 }

Set-Location -LiteralPath (Join-Path $RepoRoot 'frontend')
$env:E2E_BASE_URL = 'http://localhost'
$env:E2E_ACCEPTATION = '1'
$spec = Run ('npx playwright test --project=acceptation ' + $Spec) { npx playwright test --project=acceptation $Spec }
if ($EtapesSupplementaires) {
    $fus = Run ('fusion des etapes ' + $EtapesSupplementaires) { node e2e/acceptation/_enregistrement.js $Groupe --etapes-supplementaires $EtapesSupplementaires }
    if ($fus -ne 0) { $spec = $fus }
}
Set-Location -LiteralPath $RepoRoot
# Un enregistrement PASS couvre des ids encore en dette gelee : la dette RETRECIT d'abord
# (sinon la garde echoue sur des ids couverts restes en dette). Seulement si la spec est verte.
if ($spec -eq 0) {
    $null = Run 'python scripts/check_acceptation.py --write-baseline' { python scripts/check_acceptation.py --write-baseline }
}
$garde = Run 'python scripts/check_acceptation.py' { python scripts/check_acceptation.py }
if ($DryRun) { Write-Host ('> git add docs/audits/acceptation/' + $Groupe + '/ + captures ; git commit [dry-run]'); exit 0 }
if (($spec -ne 0) -or ($garde -ne 0)) {
    Write-Host ('ECHEC : spec=' + $spec + ' garde=' + $garde + ' - enregistrement NON commite (docs/audits/acceptation/' + $Groupe + '/, trace = rapport Playwright).')
    exit 1
}
$sha9 = (git rev-parse --short=9 HEAD).Trim()
git add -- ('docs/audits/acceptation/' + $Groupe + '/') ('docs/qa-explorer/captures/' + $Date + '/ACCEPTATION-' + $Groupe + '-*')
git commit -m ('acceptation ' + $Groupe + ' ' + $Date + '-' + $sha9)
if ($LASTEXITCODE -ne 0) { Write-Host 'ECHEC : git commit.'; exit 1 }
Write-Host ('OK - acceptation ' + $Groupe + ' ' + $Date + '-' + $sha9 + ' commitee (jamais poussee).')
exit 0
