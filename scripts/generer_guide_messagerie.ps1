# Imprime le guide « Ta messagerie TAQINOR sur Microsoft 365 » (HTML source) en PDF,
# dans docs/meryem/ (lu par `manage.py publier_documents_meryem` à chaque déploiement).
# Même commande Edge sans tête que scripts/generer_guide_suivi.py (user-data-dir unique
# obligatoire, sinon un Edge déjà ouvert avale la commande et n'écrit rien).
#
# Usage : powershell -File scripts/generer_guide_messagerie.ps1
$ErrorActionPreference = 'Stop'
$racine = Split-Path -Parent $PSScriptRoot
$html = Join-Path $racine 'docs\meryem\source\guide_messagerie_m365.html'
$pdf = Join-Path $racine 'docs\meryem\Guide_messagerie_M365.pdf'
$edge = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'Microsoft Edge introuvable.' }
if (-not (Test-Path $html)) { throw "Source introuvable : $html" }
$profil = Join-Path $env:TEMP ('edge-pdf-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $profil | Out-Null
try {
    $p = Start-Process -FilePath $edge -PassThru -Wait -ArgumentList @(
        '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
        "--user-data-dir=$profil", '--no-first-run',
        "--print-to-pdf=$pdf", ([uri]$html).AbsoluteUri)
    if ($p.ExitCode -ne 0) { throw "Edge a rendu le code $($p.ExitCode)." }
} finally {
    Remove-Item $profil -Recurse -Force -ErrorAction SilentlyContinue
}
$taille = (Get-Item $pdf).Length
if ($taille -lt 20KB) { throw "PDF suspect ($taille octets)." }
Write-Host "PDF écrit : $pdf ($taille octets)"
