import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.dev')

app = Celery('erp_agentique')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# G9 — Celery Beat. Toute la logique de temps des jobs raisonne en
# Africa/Casablanca ; on planifie donc aussi le scheduler dans ce fuseau pour
# que « 07:00 » et « minuit » soient bien des heures locales marocaines.
app.conf.timezone = 'Africa/Casablanca'
app.conf.enable_utc = False

# Deux jobs planifiés (cf. apps/ventes/scheduled.py) :
#   - contrôle quotidien des factures en retard (00:30 Casablanca),
#   - rappels de relance programmés (07:00 Casablanca).
app.conf.beat_schedule = {
    'ventes-check-overdue-factures': {
        'task': 'ventes.check_overdue_factures',
        'schedule': crontab(hour=0, minute=30),
    },
    'ventes-relance-reminders': {
        'task': 'ventes.relance_reminders',
        'schedule': crontab(hour=7, minute=0),
    },
}
