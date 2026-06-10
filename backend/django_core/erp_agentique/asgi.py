"""
ASGI config for erp_agentique project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod')

application = get_asgi_application()
