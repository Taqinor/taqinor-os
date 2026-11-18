#!/bin/bash
# Arrête tout serveur gunicorn local de reproduction (maîtres puis workers), attend la fin.
for pid in $(ps -eo pid,args | awk '/gunicorn: master|bin\/gunicorn erp_agentique/ && !/awk/ {print $1}'); do kill -TERM "$pid" 2>/dev/null; done
for i in $(seq 1 60); do ps -eo args | grep -q "^gunicorn: \|bin/gunicorn erp_agentique" || { echo "serveurs locaux arrêtés"; exit 0; }; sleep 0.5; done
for pid in $(ps -eo pid,args | awk '/gunicorn: |bin\/gunicorn erp_agentique/ && !/awk/ {print $1}'); do kill -KILL "$pid" 2>/dev/null; done
sleep 1; echo "serveurs locaux arrêtés (forcé)"
