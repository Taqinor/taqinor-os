#!/bin/bash
# Lance une commande dans l'environnement backend de la machine (sans avoir à « sourcer » env.sh) :
#   /opt/taches-cloud/run.sh python manage.py check        /opt/taches-cloud/run.sh flake8 --max-line-length=120 f.py
#   /opt/taches-cloud/run.sh python scripts/check_forme_code.py
# Variante service d'IA : TACHES_ENV=ia /opt/taches-cloud/run.sh python -m unittest -v tests.test_action_tools
set -euo pipefail
if [ "${TACHES_ENV:-erp}" = ia ]; then . /opt/taches-cloud/env-ia.sh; else . /opt/taches-cloud/env.sh; fi
export REDIS_PORT=6381   # Redis des tests et des gardes, jamais celui des piles
exec "$@"
