import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.dev')

app = Celery('erp_agentique')
app.config_from_object('django.conf:settings', namespace='CELERY')
# `autodiscover_tasks()` enregistre automatiquement le module `tasks` de chaque
# app installée — dont `apps.ventes.tasks` (PDF) et `apps.chat.tasks` (S11 :
# `chat.transcribe_voice_attachment`, le pipeline de transcription des mémos
# vocaux). Aucun enregistrement manuel n'est requis ici.
app.autodiscover_tasks()

# G9 — Celery Beat. Toute la logique de temps des jobs raisonne en
# Africa/Casablanca ; on planifie donc aussi le scheduler dans ce fuseau pour
# que « 07:00 » et « minuit » soient bien des heures locales marocaines.
app.conf.timezone = 'Africa/Casablanca'
app.conf.enable_utc = False

# Jobs planifiés (toutes les heures sont en Africa/Casablanca) :
#   - contrôle quotidien des factures en retard (00:30) — apps/ventes/scheduled.py,
#   - rappels de relance programmés (07:00) — apps/ventes/scheduled.py,
#   - QJ4 : relance cadencée des devis envoyés (08:15) — apps/ventes/scheduled.py,
#   - QJ5 : expiration automatique des devis + hygiène funnel (01:00) — apps/ventes/scheduled.py,
#   - QJ20 : rappels de rendez-vous (toutes les 15 min) — apps/ventes/scheduled.py,
#   - N76 : récapitulatif quotidien (07:30) et hebdomadaire le lundi (07:30) —
#     apps/notifications/digests.py,
#   - FG1 : balayage quotidien des EventTypes morts (08:00) —
#     apps/notifications/sweeps.py,
#   - FG2 : balayage quotidien des déclencheurs temporels d'automatisation (08:05) —
#     apps/automation/beat_tasks.py,
#   - N79 : envoi des rapports sauvegardés dus, quotidien (06:00) et
#     hebdomadaire le lundi (06:00) — apps/reporting/scheduled_reports.py.
app.conf.beat_schedule = {
    'ventes-check-overdue-factures': {
        'task': 'ventes.check_overdue_factures',
        'schedule': crontab(hour=0, minute=30),
    },
    'ventes-expire-stale-devis': {
        'task': 'ventes.expire_stale_devis',
        'schedule': crontab(hour=1, minute=0),
    },
    'crm-appointment-reminders': {
        'task': 'crm.appointment_reminders',
        'schedule': crontab(minute='*/15'),  # every 15 minutes
    },
    'ventes-relance-reminders': {
        'task': 'ventes.relance_reminders',
        'schedule': crontab(hour=7, minute=0),
    },
    'ventes-devis-followup-nudges': {
        'task': 'ventes.devis_followup_nudges',
        'schedule': crontab(hour=8, minute=15),
    },
    'notifications-daily-digest': {
        'task': 'notifications.daily_digest',
        'schedule': crontab(hour=7, minute=30),
    },
    'notifications-weekly-digest': {
        'task': 'notifications.weekly_digest',
        'schedule': crontab(hour=7, minute=30, day_of_week=1),
    },
    'notifications-sweep-daily': {
        'task': 'notifications.sweep_daily',
        'schedule': crontab(hour=8, minute=0),
    },
    'automation-time-triggers-daily': {
        'task': 'automation.time_triggers_daily',
        'schedule': crontab(hour=8, minute=5),
    },
    'reporting-email-saved-reports-daily': {
        'task': 'reporting.email_saved_reports',
        'schedule': crontab(hour=6, minute=0),
    },
    'reporting-email-saved-reports-weekly': {
        'task': 'reporting.email_saved_reports',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),
    },
}
