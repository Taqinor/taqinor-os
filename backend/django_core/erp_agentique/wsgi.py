"""
WSGI config for erp_agentique project.
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod')

# Marqueur de démarrage (journal uniquement, aucun effet UI) — sert à prouver
# que l'auto-déploiement serveur a bien rebâti et relancé le conteneur.
print('TAQINOR_AUTODEPLOY_MARKER actif', file=sys.stderr, flush=True)

application = get_wsgi_application()
