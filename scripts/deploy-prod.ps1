# Mise à jour de la PRODUCTION (serveur Hetzner) en une commande, depuis ce PC :
#   powershell -File scripts\deploy-prod.ps1
#   powershell -File scripts\deploy-prod.ps1 -ZeroDowntime   # NTPLT57 (opt-in)
#
# ADCG1 (10/11/2026) — UNE SEULE séquence de deploy : `scripts/auto-deploy.sh`.
# La production se déploie TOUTE SEULE à chaque fusion sur main (timer systemd
# `taqinor-autodeploy` du serveur, ~chaque minute). Ce script ne porte plus sa
# propre copie de la séquence (elles avaient divergé : le manuel ne redémarrait
# pas django quand seul le frontend était reconstruit, l'auto sautait six
# étapes du manuel). Il fait seulement, sur le serveur :
#   1. git fetch de main (la prod ne déploie QUE main, jamais dev) ;
#   2. installe `scripts/auto-deploy.sh` d'`origin/main` dans /opt/autodeploy/
#      (jamais la copie locale de ce PC) ;
#   3. `systemctl start taqinor-autodeploy.service` : la séquence tourne dans
#      systemd (une coupure SSH ne l'interrompt pas), et son code de sortie
#      est rendu ici.
# -ZeroDowntime pose le drapeau /opt/autodeploy/zero_downtime, lu puis effacé
# par auto-deploy.sh (bascule django à 2 répliques, voir le script).
# Le serveur est la SOURCE DE VÉRITÉ des données ; ce PC reste le dev.
# Clé SSH dédiée : %USERPROFILE%\.ssh\taqinor_hetzner (jamais dans le dépôt).
param(
    [switch]$ZeroDowntime
)

$ErrorActionPreference = 'Stop'
$ServerIp = '178.105.192.116'
$Key = "$env:USERPROFILE\.ssh\taqinor_hetzner"

$remote = @'
set -e
mkdir -p /opt/autodeploy
cd /opt/taqinor-os
git fetch origin main
git show origin/main:scripts/auto-deploy.sh > /opt/autodeploy/auto-deploy.sh.neuf
chmod +x /opt/autodeploy/auto-deploy.sh.neuf
mv /opt/autodeploy/auto-deploy.sh.neuf /opt/autodeploy/auto-deploy.sh
if [ "$ZERO_DOWNTIME" = "1" ]; then touch /opt/autodeploy/zero_downtime; fi
# ADCG3 — reessai explicite : l'auto ne rejoue jamais seul un commit en echec.
rm -f /opt/autodeploy/commit_en_echec
echo "Deploiement lance (systemctl start taqinor-autodeploy) - detail : journalctl -u taqinor-autodeploy"
# ADCG6 — imprime les lignes du journal ecrites par CE deploy : le message final
# du poste se lit dessus (ROLLBACK ou derniere ligne), il ne suppose plus rien.
N=$(wc -l < /opt/autodeploy/deploy.log 2>/dev/null || echo 0)
set +e
systemctl start taqinor-autodeploy.service
rc=$?
tail -n +"$((N + 1))" /opt/autodeploy/deploy.log 2>/dev/null
exit $rc
'@ -replace "`r`n", "`n"

# NTPLT57 — injecte l'etat du flag -ZeroDowntime en tete du script distant
# (le here-string ci-dessus est LITTERAL : on prefixe l'affectation ici).
$zdFlag = if ($ZeroDowntime) { '1' } else { '0' }
$remote = "ZERO_DOWNTIME=$zdFlag`n" + $remote

# Transport du script : FICHIER (scp) puis execution — jamais en argument ssh
# ni via stdin. Trois gotchas que ce choix evite :
#  1. CRLF: the .ps1 is CRLF on Windows; an un-normalized here-string makes the
#     remote shell see `cd /opt/taqinor-os\r` and every command fails. Hence the
#     `-replace "`r`n","`n"` above.
#  2. Do NOT pipe via stdin (`$remote | ssh ... bash -s`): a remote command that
#     reads stdin would swallow the rest of the script.
#  3. Do NOT pass the script as the ssh command ARGUMENT: Windows PowerShell 5.1
#     mangles native-command quoting on embedded double quotes in a multi-line
#     argument (« syntax error near unexpected token ( »).
# Nom unique des deux cotes (C-ADCG-008 : plus de /tmp fixe partage).
$nom = 'taqinor-deploy-' + [guid]::NewGuid().ToString('N') + '.sh'
$tmpScript = Join-Path ([IO.Path]::GetTempPath()) $nom
[IO.File]::WriteAllText($tmpScript, $remote)  # LF, sans BOM
& scp -i $Key -o StrictHostKeyChecking=accept-new $tmpScript "root@${ServerIp}:/tmp/$nom"
if ($LASTEXITCODE -ne 0) {
    Write-Error "scp du script de deploiement a echoue (code $LASTEXITCODE)."
    exit 1
}
Remove-Item $tmpScript -ErrorAction SilentlyContinue
$sortie = @()
ssh -i $Key -o StrictHostKeyChecking=accept-new "root@$ServerIp" "bash /tmp/$nom; rc=`$?; rm -f /tmp/$nom; exit `$rc" |
    ForEach-Object { Write-Host $_; $sortie += [string]$_ }
$deployExitCode = $LASTEXITCODE

# ADCG6 — le message dit ce que le JOURNAL du serveur porte, jamais une supposition
# (accents par code : ce fichier est lu en ANSI par Windows PowerShell 5.1).
if ($deployExitCode -ne 0) {
    $e = [char]0xE9; $eg = [char]0xE8; $tiret = [char]0x2014
    $rollback = $sortie | Select-String -Pattern 'ROLLBACK vers (\S+) effectu' | Select-Object -Last 1
    if ($rollback) {
        $sha = $rollback.Matches[0].Groups[1].Value
        Write-Host "`nECHEC $tiret retour arri$($eg)re vers $sha effectu$e" -ForegroundColor Red
    } else {
        $derniere = ($sortie | Where-Object { $_.Trim() } | Select-Object -Last 1) -replace '^\[[^\]]*\]\s*', ''
        Write-Host "`nECHEC SANS retour arri$($eg)re : $derniere" -ForegroundColor Red
    }
    Write-Host "Detail : /opt/autodeploy/deploy.log et journalctl -u taqinor-autodeploy." -ForegroundColor Red
    exit $deployExitCode
}

Write-Host "`nDeploiement termine. Verifiez: https://api.taqinor.ma"
