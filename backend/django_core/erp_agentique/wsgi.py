"""
WSGI config for erp_agentique project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod')

application = get_wsgi_application()
