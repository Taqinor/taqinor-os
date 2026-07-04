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
#     hebdomadaire le lundi (06:00) — apps/reporting/scheduled_reports.py,
#   - GED25 : purge automatique de la corbeille échue (02:30) — apps/ged/tasks.py
#     (DRY-RUN par défaut : n'efface rien tant que GED_PURGE_AUTO_APPLY n'est pas
#     activé ; respecte le délai de grâce + les gardes légales GED23/GED24).
#   - XGED2 : relances de signataires dus + expiration des demandes de
#     signature échues (07:45) — apps/ged/tasks.py (jamais destructif).
#   - XGED6 : contrôle périodique d'intégrité des archives légales GED23
#     (03:15) — apps/ged/tasks.py (lecture seule, jamais destructif).
#   - YLEAD14 : recyclage des leads non travaillés (SLA dépassé → escalade,
#     désassignation optionnelle au 2e seuil), toutes les heures — apps/crm/tasks.py
#     (best-effort, no-op société par société tant que lead_sla_hours=0).
#   - YSUBS1 : facturation récurrente auto (échéanciers contrats +
#     maintenance SAV dus), quotidien (02:00) — apps/contrats/scheduled.py.
#   - YSUBS2 : reconductions tacites + diffusion des alertes contrat
#     (préavis/échéance), quotidien (07:15) — apps/contrats/scheduled.py.
#   - XKB27 : messages chat programmés + rappels dus, toutes les 5 min —
#     apps/chat/tasks.py (n'envoie jamais avant l'heure choisie).
#   - XKB32 : sweep de rétention des conversations chat (02:45) —
#     apps/chat/tasks.py (sans politique active = aucune purge, journalisé
#     quand même pour traçabilité CNDP).
#   - XFAC25 : relevé de compte mensuel automatique (opt-in par client),
#     1er du mois 08:00 — apps/ventes/scheduled.py.
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
    # GED25 — purge auto de la corbeille échue (DRY-RUN par défaut, opt-in réel
    # via GED_PURGE_AUTO_APPLY). Tourne à 02:30 (heure creuse, Africa/Casablanca).
    'ged-purge-corbeille-echue': {
        'task': 'ged.purge_corbeille_echue',
        'schedule': crontab(hour=2, minute=30),
    },
    # XGED2 — relances de signataires dus + expiration des demandes échues.
    'ged-signature-relances-expiration': {
        'task': 'ged.signature_relances_expiration',
        'schedule': crontab(hour=7, minute=45),
    },
    # XGED6 — contrôle périodique d'intégrité des archives légales.
    'ged-verifier-integrite-archives': {
        'task': 'ged.verifier_integrite_archives',
        'schedule': crontab(hour=3, minute=15),
    },
    'crm-recycler-leads-non-travailles': {
        'task': 'crm.recycler_leads_non_travailles',
        'schedule': crontab(minute=0),  # every hour
    },
    # XPLT6 — évalue les alertes de seuil sur KPI agrégés (dédup interne).
    'reporting-evaluate-kpi-alertes': {
        'task': 'reporting.evaluate_kpi_alertes',
        'schedule': crontab(hour=6, minute=30),
    },
    # YSERV13 — contrôle d'intégrité inter-documents hebdomadaire (états
    # orphelins entre apps) ; notifie seulement si ≥1 anomalie détectée.
    'reporting-controle-integrite-hebdo': {
        'task': 'reporting.controle_integrite',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),
    },
    # YSUBS1 — facturation récurrente auto (échéanciers contrats +
    # maintenance SAV dus), quotidien (heure creuse).
    'contrats-generer-factures-recurrentes-dues': {
        'task': 'contrats.generer_factures_recurrentes_dues',
        'schedule': crontab(hour=2, minute=0),
    },
    # YSUBS2 — reconductions tacites + diffusion des alertes contrat
    # (préavis/échéance), quotidien.
    'contrats-reconductions-et-alertes-daily': {
        'task': 'contrats.reconductions_et_alertes_daily',
        'schedule': crontab(hour=7, minute=15),
    },
    # XKB27 — envoie les messages chat programmés dus + notifie les rappels
    # dus (« me rappeler ce message »). Cadence fine (toutes les 5 min) pour
    # qu'un message programmé parte proche de l'heure choisie, sans surcharger
    # le worker (sweep court, requêtes indexées sur `status`+date).
    'chat-send-scheduled-messages': {
        'task': 'chat.send_scheduled_messages',
        'schedule': crontab(minute='*/5'),
    },
    'chat-send-due-reminders': {
        'task': 'chat.send_due_reminders',
        'schedule': crontab(minute='*/5'),
    },
    # XKB32 — sweep de rétention des conversations (loi 09-08 / CNDP), une
    # fois par jour, heure creuse. Sans politique active, ne purge rien mais
    # journalise quand même l'exécution.
    'chat-retention-sweep': {
        'task': 'chat.retention_sweep',
        'schedule': crontab(hour=2, minute=45),
    },
    # XFAC25 — relevé de compte mensuel automatique (opt-in par client),
    # 1er du mois 08:00 Africa/Casablanca.
    'ventes-releve-mensuel-reminders': {
        'task': 'ventes.releve_mensuel_reminders',
        'schedule': crontab(hour=8, minute=0, day_of_month=1),
    },
}
