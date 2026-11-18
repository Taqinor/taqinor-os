#!/usr/bin/env bash
# TEMPORAIRE (zz-scratch-acceptation-1711) — ACEL3 et ACEL8 sur la pile compose du runner (jamais la production).
set -uo pipefail
D="$(date -u +%F)"; T="docs/audits/acceptation/ACEL/traces/$D"; mkdir -p "$T"
L3="$T/ACEL3-celery-warm-shutdown.txt"; L8="$T/ACEL8-i18n-celery-worker.txt"
dj() { docker compose exec -T django_core python manage.py shell -c "$1"; }
{ echo "# ACEL3 — runner GitHub $(date -u +%FT%TZ), sha ${GITHUB_SHA}, pile compose (.env = .env.example)"
  echo "## /proc/1/cmdline AVANT"; docker compose exec -T celery_worker cat /proc/1/cmdline | tr '\0' ' '; echo
  ID=$(dj "from core.tasks import acel3_essai_dormir; print(acel3_essai_dormir.delay(150).id)" | tail -1)
  echo "## tâche d'essai acel3_essai_dormir(150) envoyée : $ID"
  sleep 20
  echo "## état à t+20 s : $(dj "from celery.result import AsyncResult; print(AsyncResult('$ID').state)" | tail -1)"
  echo "## docker compose up -d --force-recreate celery_worker ($(date -u +%T))"
  docker compose up -d --force-recreate celery_worker 2>&1 | tail -3
  echo "## recréé à $(date -u +%T)"
  ETAT=PENDING
  for i in $(seq 1 40); do ETAT=$(dj "from celery.result import AsyncResult; print(AsyncResult('$ID').state)" | tail -1); [ "$ETAT" = SUCCESS ] && break; sleep 10; done
  echo "## état final : $ETAT ($(date -u +%T))"
  echo "## exécutions de la tâche dans les journaux (une seule attendue) :"
  docker compose logs celery_worker 2>&1 | grep -c "acel3_essai_dormir.*succeeded" || true
  docker compose logs celery_worker 2>&1 | grep -E "acel3_essai_dormir|Warm shutdown|worker: Warm" | tail -8
  echo "## /proc/1/cmdline APRÈS"; docker compose exec -T celery_worker cat /proc/1/cmdline | tr '\0' ' '; echo
} > "$L3" 2>&1
{ echo "# ACEL8 — runner GitHub $(date -u +%FT%TZ), sha ${GITHUB_SHA}"
  echo "## docker compose exec celery_worker python manage.py shell -c 'recalculer_couverture_i18n_task()'"
  docker compose exec -T celery_worker python manage.py shell -c "from core.tasks_i18n import recalculer_couverture_i18n_task; print('snapshots ecrits :', recalculer_couverture_i18n_task())"
  echo "## relu :"
  docker compose exec -T celery_worker python manage.py shell -c "from core.models import I18nCoverageSnapshot as S; from core.models import I18nCoverageSnapshot; s=S.objects.order_by('-calcule_le').first(); print('SNAP', s and s.semaine, s and s.composants_total, s and s.couverture_pct)"
  echo "## montages : $(docker compose exec -T celery_worker ls /opt/scripts/extract_i18n_strings.py /opt/frontend/src 2>&1 | head -2 | tr '\n' ' ')"
} > "$L8" 2>&1
cat "$L3" "$L8"
python3 - "$D" "$L3" "$L8" <<'PY'
import json, re, sys
D, l3, l8 = sys.argv[1:]
t3, t8 = open(l3, encoding='utf-8').read(), open(l8, encoding='utf-8').read()
NA = {str(i): 'NA' for i in range(1, 11)}
av = re.search(r'## /proc/1/cmdline AVANT\n(.*)', t3); ap = re.search(r'## /proc/1/cmdline APRÈS\n(.*)', t3)
fin = re.search(r'## état final : (\S+)', t3); n = re.search(r'une seule attendue\) :\n(\d+)', t3)
ok3 = bool(av and ap and av.group(1).startswith('celery') and ap.group(1).startswith('celery') and fin and fin.group(1) == 'SUCCESS' and n and n.group(1) == '1')
m = re.search(r'SNAP (\S+) (\d+) ', t8)
ok8 = bool(m and int(m.group(2)) > 0)
R = 'runner GitHub ubuntu-latest, pile docker compose (.env = .env.example), jamais la production'
et = [
 {'id': 'COMPOSE-ACEL3-warm-shutdown', 'taches': ['ACEL3'], 'verdict': 'PASS' if ok3 else 'FAIL', 'base_verdict': None, 'corps': 'PASS' if ok3 else 'FAIL', 'trace': l3, 'oracles': NA,
  'notes': f"{R} ; tâche d'essai qui dort 150 s (ajoutée à core/tasks.py sur le seul checkout du runner, jamais commitée) en cours, puis `docker compose up -d --force-recreate celery_worker` : état final {fin.group(1) if fin else '?'}, exécutions {n.group(1) if n else '?'} ; /proc/1/cmdline avant « {av.group(1)[:60] if av else '?'} », après « {ap.group(1)[:60] if ap else '?'} » ; non-ré-exécution une heure plus tard non observable dans le temps du job (une seule exécution au journal)"},
 {'id': 'COMPOSE-ACEL8-i18n-celery-worker', 'taches': ['ACEL8'], 'verdict': 'PASS' if ok8 else 'FAIL', 'base_verdict': None, 'corps': 'PASS' if ok8 else 'FAIL', 'trace': l8, 'oracles': NA,
  'notes': f"{R} ; `docker compose exec celery_worker python manage.py shell -c recalculer_couverture_i18n_task()` puis relu : I18nCoverageSnapshot semaine {m.group(1) if m else '?'}, composants {m.group(2) if m else '?'}"}]
json.dump({'couvre': ['ACEL3', 'ACEL8'], 'etapes': et}, open('/tmp/etapes-ACEL.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ACEL3', ok3, 'ACEL8', ok8)
PY
