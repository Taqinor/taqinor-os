#!/usr/bin/env bash
# Garde machine PC2 (Reda, 28/10 : « monitor the machine and docker usage, cpu and RAM and disk »).
# Usage : guard.sh            → une mesure
#         guard.sh <minutes>  → attend d'abord N minutes puis mesure
# Seuils (README passation §3.4 + registre PC1) : RAM libre < 5 Go → ALERTE (arrêter le tour des 2 sessions
# les plus récentes hors jeton) ; < 4 Go → aussi clore la fenêtre Docker en cours ;
# claude > 30 ou node > 60 → ALERTE ; disque C: < 10 Go → ALERTE ; CPU > 90 % → signalé.
if [ -n "$1" ]; then end=$(( $(date +%s) + $1*60 )); until [ $(date +%s) -ge $end ]; do sleep 30; done; fi
echo "=== GUARD $(date -u +%H:%M) UTC ==="
powershell -NoProfile -Command '
$os=Get-CimInstance Win32_OperatingSystem
$free=[math]::Round($os.FreePhysicalMemory/1MB,1); $tot=[math]::Round($os.TotalVisibleMemorySize/1MB,1)
$cpu=(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$d=Get-PSDrive C; $dfree=[math]::Round($d.Free/1GB,1)
$cl=@(Get-Process claude -ErrorAction SilentlyContinue); $nd=@(Get-Process node -ErrorAction SilentlyContinue); $py=@(Get-Process python -ErrorAction SilentlyContinue)
$clmb=[math]::Round((($cl | Measure-Object WorkingSet64 -Sum).Sum)/1MB); $ndmb=[math]::Round((($nd | Measure-Object WorkingSet64 -Sum).Sum)/1MB)
$vm=(Get-Process vmmem -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum/1MB
"RAM free {0} / {1} GB | CPU {2}% | DISK C: {3} GB free | claude {4} ({5} MB) | node {6} ({7} MB) | python {8} | docker VM {9:N0} MB" -f $free,$tot,$cpu,$dfree,$cl.Count,$clmb,$nd.Count,$ndmb,$py.Count,$vm
$al=@()
if ($free -lt 4) { $al += "RAM<4GB" } elseif ($free -lt 5) { $al += "RAM<5GB" }
if ($cl.Count -gt 30) { $al += "claude>30" }
if ($nd.Count -gt 60) { $al += "node>60" }
if ($dfree -lt 10) { $al += "DISK<10GB" }
if ($cpu -gt 90) { $al += "CPU>90" }
if ($al.Count) { "ALERTE: " + ($al -join ",") } else { "OK" }
'
echo "--- docker ---"
timeout 60 docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' 2>/dev/null | grep -v -E '^erp-agentique-(frontend|nginx|redis|redis_cache|fastapi-stub|minio)-?1? '
run=$(timeout 30 docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -v '^erp-agentique-\(frontend\|nginx\|django_core\|fastapi_ia\|db\|fastapi-stub\|minio\|redis_cache\|redis\)-1' | tr '\n' ';')
[ -n "$run" ] && echo "conteneurs hors pile: $run" || echo "conteneurs hors pile: aucun"
timeout 60 docker system df --format '{{.Type}} {{.Size}} reclaimable={{.Reclaimable}}' 2>/dev/null | head -4
