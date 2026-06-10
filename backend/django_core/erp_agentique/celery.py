import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.dev')

app = Celery('erp_agentique')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
