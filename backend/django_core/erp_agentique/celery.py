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

# INCIDENT PROD 14/09/2026 — 42 tâches du beat_schedule n'étaient JAMAIS
# enregistrées côté worker : `autodiscover_tasks()` n'importe que le module
# `tasks` de chaque app, or plusieurs apps déclarent leurs tâches beat dans
# des modules dédiés (scheduled.py, beat_tasks.py, sweeps.py, digests.py,
# scheduled_reports.py) que rien n'importait au boot du worker. Beat les
# envoyait quand même → « unregistered task » en boucle, file `scheduled`
# engorgée, et les fonctionnalités (relances devis/factures, rappels de
# rendez-vous, digests, reprises d'automatisation NTEXT7) silencieusement
# mortes. On étend l'autodécouverte à ces modules conventionnels ; le test
# gardien core/tests/test_celery_task_routes.py (tâche planifiée ⇒ tâche
# enregistrée) refuse toute nouvelle divergence.
for _related_name in ('scheduled', 'beat_tasks', 'sweeps', 'digests',
                      'scheduled_reports',
                      # NTI18N39 — `core/tasks_i18n.py` : module de tâche dédié
                      # (core/tasks.py appartient à une autre lane). Aucun des
                      # cinq noms conventionnels ci-dessus ne le couvre, donc
                      # sans cette entrée le worker ne l'importerait jamais et
                      # `core.recalculer_couverture_i18n` serait « unregistered
                      # task » — exactement l'incident du 14/09/2026.
                      'tasks_i18n'):
    app.autodiscover_tasks(related_name=_related_name)

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
#   - XFSM6 : rappel client J-1 pour les interventions non confirmées
#     (07:45) — apps/installations/tasks.py (brouillon wa.me responsable +
#     email client, key-gated, jamais d'envoi WhatsApp automatique).
#   - YHIRE8 : alertes d'expiration RH (habilitations/certifs/docs/visites/EPI,
#     07:50) et alerte fin de CDD (07:55) — apps/rh/tasks.py (idempotent par
#     jour+échéance, jamais avant branché sur le beat).
#   - YSERV5 : génération automatique des visites préventives dues (07:45) —
#     apps/sav/tasks.py (opt-in par société, OFF par défaut = no-op ;
#     réutilise generer_visites_dues, idempotent).
#   - NTSAN31 : alerte J-7 avant expiration d'une PriseEnCharge santé (07:40)
#     — apps/sante/tasks.py (idempotent par jour+PriseEnCharge, miroir du
#     pattern apps/rh/tasks.py alertes_expiration).
#   - NTEDU22 : matérialisation hebdomadaire des séances depuis l'emploi du
#     temps actif (dimanche 20:00, fériés marocains exclus) — apps/education/
#     tasks.py (idempotent par classe/matière/date/heure de début).
#   - NTIDE40 : digest feedback produit non-lu par thème (08:40), gated PAR
#     SOCIÉTÉ (InnovationSettings.feedback_digest_actif, désactivé par
#     défaut) — apps/innovation/tasks.py (no-op tant qu'aucune société ne
#     l'active ; la fréquence hebdo, elle, ne notifie que le lundi).
#   - WIR73 : import GED hebdomadaire des pièces jointes éparses (idempotent,
#     lundi 03:25) — apps/ged/tasks.py (`migrate_attachments_to_ged`, GED7).
#   - WIR148 : génération quotidienne de l'échéancier de loyer des baux actifs
#     (idempotent, 02:38) — apps/immobilier/tasks.py.
#
# N4 (décision fondateur du 25/09/2026) — AUCUNE NOTIFICATION UTILISATEUR LA
# NUIT. Une tâche de nuit ou « toutes les N minutes » peut tourner à toute
# heure : ce qu'elle notifie passe par `notifications.services.notify()`, qui
# REPORTE au prochain créneau ouvré de la société (N1 — la notification est
# créée, puis livrée par `notifications.livrer_differees`). Seules les
# alertes de SÉCURITÉ contournent le report (`respect_quiet_hours=False`) :
# une tâche planifiée la nuit qui en émet est DÉPLACÉE dans la fenêtre
# (NTSEC25, comptes dormants, 02:20 → 08:50). Une nouvelle tâche qui écrit
# une `Notification` sans `notify()` n'est PAS couverte par le report.
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
    # CRX22 — rafraîchissement quotidien du score des leads NON TOUCHÉS. Le
    # score n'était recalculé qu'à l'édition : la décote de récence (12 pts le
    # premier jour → 1 pt au-delà de 90 jours) ne s'appliquait jamais à un
    # lead dormant, qui restait « chaud » pour toujours — et le tri par score
    # remontait des leads de six mois au-dessus de leads du jour. Passage à
    # 4 h 10, avant les relances et digests du matin, qui lisent ce score.
    'crm-recalculer-scores-obsoletes': {
        'task': 'crm.recalculer_scores_obsoletes',
        'schedule': crontab(hour=4, minute=10),
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
    # VX210 — réveille les items snoozés (activités + approbations) dont
    # l'échéance de snooze est passée ; toutes les 30 min pour un réveil prompt.
    'notifications-reveiller-snoozes': {
        'task': 'notifications.reveiller_snoozes',
        'schedule': crontab(minute='*/30'),
    },
    # N1 (décision fondateur 25/09/2026) — livre les notifications DIFFÉRÉES :
    # émises hors de la fenêtre de travail de leur société, elles sont créées
    # mais attendent le prochain créneau ouvré. Toutes les 5 min : une
    # notification de nuit arrive au plus 5 min après l'ouverture. Sans
    # échéance due, no-op (une requête sur un index partiel).
    'notifications-livrer-differees': {
        'task': 'notifications.livrer_differees',
        'schedule': crontab(minute='*/5'),
    },
    # VX209(c) — purge/archive quotidienne des notifications anciennes (lues
    # > 60 j supprimées, non-lues > 60 j archivées) ; heure creuse.
    'notifications-purge-anciennes': {
        'task': 'notifications.purge_notifications_anciennes',
        'schedule': crontab(hour=2, minute=45),
    },
    # NTI18N37 — rappel quotidien (novembre-décembre uniquement) de saisie
    # des 4 fêtes mobiles de l'année suivante ; s'arrête de lui-même dès que
    # la saisie est complète (voir apps/notifications/tasks.py).
    'notifications-rappel-fetes-mobiles': {
        'task': 'notifications.rappel_fetes_mobiles',
        'schedule': crontab(hour=7, minute=40, month_of_year='11,12'),
    },
    # NTPLT10 — filet beat de l'outbox : livre les événements pending/failed
    # échus (en plus de l'enqueue on_commit immédiat) toutes les 5 minutes.
    'core-dispatch-outbox': {
        'task': 'core.dispatch_outbox',
        'schedule': crontab(minute='*/5'),
    },
    # NTPLT36 — crée les partitions mensuelles à l'avance (M + M+1 + M+2,
    # idempotent) ; une passe quotidienne suffit largement.
    'core-ensure-partitions': {
        'task': 'core.ensure_partitions',
        'schedule': crontab(hour=3, minute=0),
    },
    # NTPLT8 — scan MENSUEL DRY-RUN d'étanchéité des données vivantes
    # (company_id NULL/orphelin) ; le 1er du mois, ne modifie rien.
    'core-scan-live-isolation': {
        'task': 'core.scan_live_isolation',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),
    },
    'automation-time-triggers-daily': {
        'task': 'automation.time_triggers_daily',
        'schedule': crontab(hour=8, minute=5),
    },
    # NTEXT7 — reprise des séquences d'automatisation suspendues par une étape
    # « Attendre » (toutes les 5 min ; sans échéance due, no-op total).
    'automation-process-due-steps': {
        'task': 'automation.process_due_automation_steps',
        'schedule': crontab(minute='*/5'),
    },
    # AUD231 — UNE seule entrée. Il y en avait DEUX pour la même tâche sans
    # argument (`…-daily` à 6 h 00 et `…-weekly` lundi 6 h 00) : la tâche
    # décide elle-même des rapports dus (`_due_schedules`, toutes cadences
    # confondues — apps/reporting/scheduled_reports.py), donc l'entrée
    # hebdomadaire ne faisait que la rejouer une 2ᵉ fois chaque lundi à la même
    # minute. L'entrée quotidienne couvre déjà le lundi.
    'reporting-email-saved-reports-daily': {
        'task': 'reporting.email_saved_reports',
        'schedule': crontab(hour=6, minute=0),
    },
    # NTEXT12 — abonnements aux rapports (report-builder). Tourne à CHAQUE
    # heure pile : le `cron` de chaque abonnement décide s'il est dû (grain =
    # l'heure ; voir apps/reporting/rapport_abonnements.py). No-op complet tant
    # qu'aucun abonnement actif n'est dû.
    'reporting-envoyer-rapports-planifies': {
        'task': 'reporting.envoyer_rapports_planifies',
        'schedule': crontab(minute=0),
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
    # ZGED14 — notifie les ÉMETTEURS de demandes de signature dont
    # l'expiration approche (versant émetteur, complète XGED2 ci-dessus).
    'ged-notifier-emetteurs-expiration-signature': {
        'task': 'ged.notifier_emetteurs_expiration_signature',
        'schedule': crontab(hour=8, minute=0),
    },
    # XGED8 (AUDV12) — relance en masse les DemandeDocument en attente
    # (documentée « à planifier », jamais câblée jusqu'ici).
    'ged-relancer-demandes-document-dues': {
        'task': 'ged.relancer_demandes_document_dues',
        'schedule': crontab(hour=8, minute=15),
    },
    # XGED15 (AUDV12) — notifie les assignés des planifications de document
    # échues (documentée « à planifier », jamais câblée jusqu'ici).
    'ged-notifier-planifications-echues': {
        'task': 'ged.notifier_planifications_echues',
        'schedule': crontab(hour=8, minute=30),
    },
    'crm-recycler-leads-non-travailles': {
        'task': 'crm.recycler_leads_non_travailles',
        'schedule': crontab(minute=0),  # every hour
    },
    # MRY0 (lot C) — miroir Odoo → ERP. Il n'était planifié NULLE PART : le
    # cockpit de Meryem décrochait silencieusement (dernière passe 01/09/2026).
    # No-op propre sans config Odoo ni ODOO_SYNC_COMPANY_SLUG ; verrou interne
    # contre deux passes simultanées. Odoo reste en LECTURE SEULE.
    'crm-sync-odoo-leads': {
        'task': 'crm.sync_odoo_leads',
        'schedule': crontab(minute='*/30'),
    },
    # MRY17 — digest du matin : « N relance(s) à faire aujourd'hui », UNE
    # fois par jour et par commercial (idempotent par jour). Le panneau
    # « Relances du jour » ne sert à rien si personne ne l'ouvre.
    'crm-notifier-relances-dues': {
        'task': 'crm.notifier_relances_dues',
        'schedule': crontab(hour=8, minute=30),
    },
    # MRY17 — surveillance de la promesse « rappelé en moins de cinq minutes
    # OUVRÉES ». Toutes les 5 min ; hors fenêtre d'appel, zéro minute ouvrée
    # s'écoule, donc aucune escalade la nuit.
    'crm-escalader-premier-contact': {
        'task': 'crm.escalader_premier_contact',
        'schedule': crontab(minute='*/5'),
    },
    # MRY21 — bilan hebdomadaire du moteur de relances, lundi 07:00, à la
    # direction. Sept chiffres : la seule vue de HAUT du moteur.
    'crm-bilan-hebdo-relances': {
        'task': 'crm.bilan_hebdo_relances',
        'schedule': crontab(hour=7, minute=0, day_of_week=1),
    },
    # QW4 — SLA rappel plus serré que le SLA générique premier-contact :
    # tourne plus souvent (toutes les 30 min) pour rattraper une escalade
    # rapidement sur un SLA rappel typiquement court (2 à quelques heures).
    'crm-escalader-rappels-demandes': {
        'task': 'crm.escalader_rappels_demandes',
        'schedule': crontab(minute='*/30'),
    },
    # NTCRM6 — snapshot forecast hebdomadaire (glissement visible dans le
    # temps) ; idempotent (upsert par semaine ISO + owner), lundi tôt matin.
    'crm-snapshot-forecast-hebdo': {
        'task': 'crm.snapshot_forecast_hebdo',
        'schedule': crontab(hour=5, minute=0, day_of_week=1),
    },
    # XPLT6 — évalue les alertes de seuil sur KPI agrégés (dédup interne).
    'reporting-evaluate-kpi-alertes': {
        'task': 'reporting.evaluate_kpi_alertes',
        'schedule': crontab(hour=6, minute=30),
    },
    # NTDATA42 — signale les points aberrants des séries de métriques nommées
    # (z-score sur `core.anomaly` → `core.AnomalyFlag`). HEBDOMADAIRE : les
    # séries sont MENSUELLES, un balayage quotidien re-scorerait les mêmes
    # points douze fois par mois pour rien. Aucun seuil à configurer, aucune
    # notification — un AnomalyFlag se consulte.
    'semantic-detecter-anomalies-metriques': {
        'task': 'semantic.detecter_anomalies_metriques',
        'schedule': crontab(hour=4, minute=45, day_of_week=1),
    },
    # YSERV13 — contrôle d'intégrité inter-documents hebdomadaire (états
    # orphelins entre apps) ; notifie seulement si ≥1 anomalie détectée.
    'reporting-controle-integrite-hebdo': {
        'task': 'reporting.controle_integrite',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),
    },
    # XFAC25 — relevé de compte mensuel automatique (opt-in par client),
    # 1er du mois 08:00 Africa/Casablanca.
    'ventes-releve-mensuel-reminders': {
        'task': 'ventes.releve_mensuel_reminders',
        'schedule': crontab(hour=8, minute=0, day_of_month=1),
    },
    # XFSM6 — rappel client J-1 (interventions non confirmées, demain).
    'installations-rappel-rdv-j1': {
        'task': 'installations.rappel_rdv_j1',
        'schedule': crontab(hour=7, minute=45),
    },
    # YSERV5 — génération automatique des visites préventives dues (opt-in
    # par société via SavSlaSettings.generation_auto_visites), quotidien.
    'sav-generer-visites-dues-quotidien': {
        'task': 'sav.generer_visites_dues_quotidien',
        'schedule': crontab(hour=7, minute=45),
    },
    # WIR30 — pré-alerte SLA (J-x) + escalade à la violation (XSAV6,
    # apps/sav/views.py scan_sla_pre_alerts_and_escalations), bâtie/testée
    # mais jamais planifiée jusqu'ici. DISTINCT de scan_sla_breaches
    # (planifiée séparément juste en dessous). OFF par défaut par société
    # (sla_warning_days=0, escalade_activee=False) : no-op tant qu'aucun
    # réglage n'est activé.
    # NTSRV38 — cadence relevée de quotidienne à TOUTES LES 15 MINUTES : les
    # paliers d'escalade multi-niveaux (NTSRV12) vivent dans cette fonction,
    # et un palier « J+1 → direction » n'a aucun sens s'il n'est rescanné
    # qu'une fois par jour. Le balayage est idempotent par ticket et deux
    # exécutions concurrentes sont exclues par un verrou (apps/sav/tasks.py).
    'sav-scan-sla-pre-alerts-and-escalations': {
        'task': 'sav.scan_sla_pre_alerts_and_escalations_quotidien',
        'schedule': crontab(minute='*/15'),
    },
    # NTSRV38 — violation SLA (FG81, apps/sav/views.py scan_sla_breaches) :
    # bâtie et testée mais SANS aucune entrée beat jusqu'ici (elle ne tournait
    # qu'à la demande). Décalée de 7 minutes sur le quart d'heure pour ne pas
    # balayer les tickets en même temps que la tâche ci-dessus. OFF par
    # société tant que sla_breach_enabled est False (défaut).
    'sav-scan-sla-breaches-quart-heure': {
        'task': 'sav.scan_sla_breaches_quart_heure',
        'schedule': crontab(minute='7,22,37,52'),
    },
    # XFSM21 — météo J+3 sur les poses planifiées (Open-Meteo, gratuit,
    # sans clé), quotidien, heure creuse matinale.
    'installations-meteo-planning-j3': {
        'task': 'installations.meteo_planning_j3',
        'schedule': crontab(hour=6, minute=30),
    },
    # NTP2P33 — relance RFQ non répondue à J-2 de la date limite de réponse.
    'installations-relancer-rfq-en-attente': {
        'task': 'installations.relancer_rfq_en_attente',
        'schedule': crontab(hour=7, minute=15),
    },
    # NTP2P35 — archivage MENSUEL des brouillons de demande d'achat abandonnés
    # (> seuil société, défaut 90 j). Jamais de suppression dure, jamais un
    # brouillon épinglé ; heure creuse du 1er du mois.
    'installations-purger-demandes-achat-brouillon': {
        'task': 'installations.purger_demandes_achat_brouillon',
        'schedule': crontab(hour=3, minute=55, day_of_month=1),
    },
    # ZSTK1 — recompute réappro + alertes de rupture (« reordering rules
    # run » façon Odoo), quotidien, heure creuse matinale. Suggestion
    # seulement (aucun BCF créé automatiquement), idempotent par société.
    'stock-recompute-reordering': {
        'task': 'stock.recompute_reordering',
        'schedule': crontab(hour=6, minute=15),
    },
    # ZPUR7 — brouillon de relance BCF en retard (gated OFF par défaut via
    # `AchatsParametres.relance_bcf_actif`, no-op tant que non activé).
    'stock-relancer-bcf-en-retard': {
        'task': 'stock.relancer_bcf_en_retard',
        'schedule': crontab(hour=7, minute=10),
    },
    # ZSTK2 — alertes de péremption des lots (fenêtre configurable par
    # société, `CompanyProfile.jours_alerte_peremption`, défaut 30).
    'stock-expiration-alerts': {
        'task': 'stock.expiration_alerts',
        'schedule': crontab(hour=6, minute=20),
    },
    # NTWMS42 — alerte PASSIVE de sur-stockage par zone (seuil 95 % par
    # défaut). Une zone sans capacité déclarée n'est jamais signalée, donc
    # no-op tant qu'aucune `CategorieStockage` n'est posée sur les casiers.
    'stock-alerter-surcapacite-zones': {
        'task': 'stock.alerter_surcapacite_zones',
        'schedule': crontab(hour=6, minute=25),
    },
    # XPUR1 (AUDV04) — documents de conformité fournisseur expirant sous 30
    # jours : `notify_expiring_conformite_documents` existait déjà, testée,
    # mais sans aucun cron pour la déclencher.
    'stock-notifier-documents-conformite-expirants': {
        'task': 'stock.notifier_documents_conformite_expirants',
        'schedule': crontab(hour=6, minute=35),
    },
    # XPUR7 (AUDV04) — alerte ACHETEUR (BCF_LATE) des BCF ENVOYE en retard,
    # distincte de la relance fournisseur ZPUR7 ci-dessus.
    'stock-notifier-bcf-en-retard-buyer': {
        'task': 'stock.notifier_bcf_en_retard_buyer',
        'schedule': crontab(hour=6, minute=40),
    },
    # NTP2P20 — pieces d'onboarding fournisseur (NTP2P7, DocumentFournisseur)
    # expirant sous 30 jours ; distincte du sweep XPUR1 juste au-dessus
    # (DocumentConformiteFournisseur, registre sans fichier).
    'stock-notifier-documents-fournisseur-expirants': {
        'task': 'stock.notifier_documents_fournisseur_expirants',
        'schedule': crontab(hour=6, minute=37),
    },
    # NTP2P34 — recalcule quotidiennement le score de risque (NTP2P8) de
    # tous les fournisseurs actifs ; calcul pur, aucun cache à invalider.
    'stock-recompute-scores-risque': {
        'task': 'stock.recompute_scores_risque',
        'schedule': crontab(hour=6, minute=45),
    },
    # YOPSB1 — pg_dump réel quotidien vers MinIO (heure creuse).
    'core-dump-database': {
        'task': 'core.dump_database',
        'schedule': crontab(hour=3, minute=0),
    },
    # YOPSB2 — drill de restauration hebdomadaire (lundi, heure creuse),
    # restaure dans une base JETABLE et vérifie des comptages clés.
    'core-restore-drill': {
        'task': 'core.restore_drill',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),
    },
    # YOPSB3 — purge GFS quotidienne des dumps (DRY-RUN sauf
    # BACKUP_PURGE_AUTO_APPLY).
    'core-purge-backups': {
        'task': 'core.purge_backups',
        'schedule': crontab(hour=5, minute=0),
    },
    # YOPSB10 — sweep quotidien de toutes les politiques de rétention
    # enregistrées (DRY-RUN sauf RETENTION_AUTO_APPLY), heure creuse.
    'core-run-retention': {
        'task': 'core.run_retention',
        'schedule': crontab(hour=2, minute=0),
    },
    # YHARD6 — heartbeat du beat (toutes les 5 min) : alimente /metrics et
    # core/health.py (détection d'un beat arrêté).
    'core-beat-heartbeat': {
        'task': 'core.beat_heartbeat',
        'schedule': crontab(minute='*/5'),
    },
    # NTPLT6 — metering d'usage par tenant, instantané nocturne (idempotent,
    # comptages bornés) ; fondation de N100 (plans/billing, différé).
    'core-snapshot-tenant-usage': {
        'task': 'core.snapshot_tenant_usage',
        'schedule': crontab(hour=1, minute=45),
    },
    # YAPIC10 — purge quotidienne des IdempotencyRecord (YAPIC9) plus vieux
    # que 24 h, heure creuse.
    'core-purge-idempotency-records': {
        'task': 'core.purge_idempotency_records',
        'schedule': crontab(hour=3, minute=15),
    },
    # YSERV3 — balayage monitoring quotidien (synchro fournisseur + évaluation
    # de sous-performance), heure creuse matinale.
    'monitoring-balayage-quotidien': {
        'task': 'monitoring.balayage_quotidien',
        'schedule': crontab(hour=7, minute=35),
    },
    # ── QX11 — jobs périodiques BÂTIS mais JAMAIS planifiés (bug dominant :
    # une tâche testée mais absente du beat ne tourne jamais). Ajoutés à des
    # créneaux heures creuses ; un test de garde (test_qx11_beat_reachability)
    # échoue désormais si un nouveau @shared_task périodique reste hors beat.
    # XFAC7 — rappels J-N avant échéance de tranche (devis accepté).
    'ventes-pre-echeance-reminders': {
        'task': 'ventes.pre_echeance_reminders',
        'schedule': crontab(hour=7, minute=20),
    },
    # ZFAC12 — « accepté mais jamais facturé » : nudge le facturier.
    'ventes-devis-a-facturer-reminder': {
        'task': 'ventes.devis_a_facturer_reminder',
        'schedule': crontab(hour=7, minute=25),
    },
    # QX36 — relève des boîtes email entrantes (dispatch bus core.email_intake :
    # SAV email→ticket, ventes réponse→devis). No-op sans boîte configurée.
    'ventes-poll-inbound-mailboxes': {
        'task': 'ventes.poll_inbound_mailboxes',
        'schedule': crontab(minute='*/10'),
    },
    # QX36 — FG373 relève GED (import documentaire par email), toutes les 10 min.
    'ged-poll-mail-intake': {
        'task': 'ged.poll_mail_intake',
        'schedule': crontab(minute='*/10'),
    },
    # QX30be — moteur de relance déclenchée par le comportement (non-ouverture
    # 24 h / ouvert-non-signé 48 h / rouvert 3×). Toutes les 3 h.
    'ventes-engagement-followup-engine': {
        'task': 'ventes.engagement_followup_engine',
        'schedule': crontab(minute=5, hour='*/3'),
    },
    # QX31be — escalade speed-to-lead : lead chaud dont la notif d'arrivée
    # reste non lue au-delà du seuil minutes. Cadence rapide (toutes les 15 min).
    'notifications-sweep-hot-leads': {
        'task': 'notifications.sweep_hot_leads',
        'schedule': crontab(minute='*/15'),
    },
    # ENG6 — synchro quotidienne des insights publicitaires (miroirs +
    # snapshots). NO-OP propre tant qu'aucune MetaConnection n'est activée.
    'adsengine-sync-insights-daily': {
        'task': 'adsengine.sync_insights_daily',
        'schedule': crontab(hour=6, minute=45),
    },
    # ENG11 — brief hebdomadaire déterministe (lundi, heure creuse). Ne génère
    # un brief que pour les sociétés ayant des campagnes ; idempotent.
    'adsengine-generate-weekly-brief': {
        'task': 'adsengine.generate_weekly_brief',
        'schedule': crontab(hour=6, minute=50, day_of_week=1),
    },
    # ADSDEEP62 — digest QUOTIDIEN FR (dépense/conversations/leads/signatures/
    # alertes actives/top ad de la veille), après le brief. NO-OP propre sans
    # campagne synchronisée ; opt-out par utilisateur respecté (EventType.DIGEST).
    'adsengine-daily-ads-digest': {
        'task': 'adsengine.daily_ads_digest',
        'schedule': crontab(hour=6, minute=58),
    },
    # ADSENG15 — boucle CRITIQUE du Gardien (toutes les 6 h) : garde-fous
    # sécurité (zéro-diffusion, ad refusée, pic/chute de dépense). JAMAIS
    # sub-horaire (rate limits Meta scalés au spend, dd-guardian §A9).
    'adsengine-evaluate-guardrails': {
        'task': 'adsengine.evaluate_guardrails',
        'schedule': crontab(minute=15, hour='*/6'),
    },
    # ADSENG15 — boucle d'OPTIMISATION du Gardien (quotidienne, après la synchro
    # ENG6 de 06:45) : fatigue créative, bande CPL, backlog bas.
    'adsengine-evaluate-optimization-rules': {
        'task': 'adsengine.evaluate_optimization_rules',
        'schedule': crontab(hour=6, minute=55),
    },
    # ADSDEEP42 — boucle QUART-HORAIRE du Gardien : évalue les règles opt-in
    # (RulePolicy.cadence_minutes>0), bornée par le budgeteur de rate-limit
    # ADSDEEP5 (jamais un 613). NO-OP tant qu'aucune règle n'a opté.
    'adsengine-evaluate-quarter-hourly': {
        'task': 'adsengine.evaluate_quarter_hourly',
        'schedule': crontab(minute='*/15'),
    },
    # ADSENG35 — boucle du FlightRunner (quotidienne, après le gardien de 06:55).
    # NO-OP par défaut : ne tourne que pour les sociétés ayant ACTIVÉ le mode
    # autonome (préflight ADSENG38 vert) et sans interrupteur global engagé.
    'adsengine-run-active-flightplans': {
        'task': 'adsengine.run_active_flightplans',
        'schedule': crontab(hour=7, minute=5),
    },
    # ASG2 — oubli HEBDO des posteriors de l'arbre d'hypothèses (péremption §3.2 :
    # chaque semaine sans test, (α,β) s'oublie vers le prior à la demi-vie de la
    # classe). Lundi tôt, avant les boucles du gardien/runner. NO-OP sans nœud.
    'adsengine-decay-assumptions-weekly': {
        'task': 'adsengine.decay_assumptions_weekly',
        'schedule': crontab(hour=6, minute=40, day_of_week=1),
    },
    # ADSDEEP8 — synchro HEBDO des breakdowns (âge×genre, placements, régions,
    # heures) des campagnes miroir. Lundi, heure creuse. NO-OP sans connexion Meta.
    'adsengine-sync-breakdowns-weekly': {
        'task': 'adsengine.sync_breakdowns_weekly',
        'schedule': crontab(hour=7, minute=15, day_of_week=1),
    },
    # PUB94 — snapshot HEBDO d'observabilité de L'Arbre : flag « branche morte »
    # (nœud figé sur son prior depuis N semaines). Lundi, après l'oubli hebdo.
    # Alerte INFO brake-only, jamais un re-test auto. NO-OP propre sans nœud.
    'adsengine-flag-dead-branches-weekly': {
        'task': 'adsengine.flag_dead_branches_weekly',
        'schedule': crontab(hour=6, minute=50, day_of_week=1),
    },
    # ADSDEEP18 — pull-sync QUOTIDIEN des leads lead-form (convergence avec le
    # webhook, idempotent par leadgen_id). NO-OP propre sans connexion Meta live.
    'adsengine-pull-meta-leads': {
        'task': 'adsengine.pull_meta_leads',
        'schedule': crontab(hour=7, minute=25),
    },
    # MRY0 (lot B) — FILET de rattrapage toutes les 15 min (fenêtre 48 h). Le
    # webhook temps réel reste le chemin nominal ; ce filet borne le retard
    # maximal à 15 min quand il tombe en panne (incident AZIZ : 22 h de retard
    # parce que seul le pull de 07:25 pouvait faire entrer le lead).
    'adsengine-pull-meta-leads-recent': {
        'task': 'adsengine.pull_meta_leads_recent',
        'schedule': crontab(minute='*/15'),
    },
    # ADSDEEP27 — boucle de retour CAPI « signatures » (CRM Dataset Meta) : push
    # QUOTIDIEN de l'événement signed_contract par deal signé Odoo, idempotent
    # (marqueur CapiOdooEvent). NO-OP propre sans CAPI_CRM_DATASET_ID + token.
    'adsengine-emit-capi-signatures': {
        'task': 'adsengine.emit_capi_signatures',
        'schedule': crontab(hour=7, minute=35),
    },
    # PUB89 — score QUOTIDIEN de qualité de la chaîne d'attribution (complétude
    # de jointure de la récompense proxy CtwaReferral) : alerte BRAKE-ONLY sous
    # seuil, jamais une pause auto. NO-OP propre sans référence CTWA.
    'adsengine-check-attribution-quality': {
        'task': 'adsengine.check_attribution_quality',
        'schedule': crontab(hour=7, minute=45),
    },
    # ── lane/gen-b — AGEN8 : auto-pause maison du rayon d'explosion (bloc isolé,
    # fold propre avec le co-éditeur de celery.py). Polling COURT (toutes les
    # 30 min) de effective_status des créatifs générés : un refus Meta est mis
    # en PAUSE dans le cycle courant (Meta n'offre aucune auto-pause native).
    # NO-OP propre tant qu'aucun créatif généré n'est surveillé.
    'adsengine-autopause-blast-radius': {
        'task': 'adsengine.autopause_blast_radius',
        'schedule': crontab(minute='*/30'),
    },
    # PUB15 — détecteur HEBDO de divergence CRM/proxy du bandit (ADSENG9). Lundi
    # (après les autres boucles hebdo). Une divergence proxy/CRM ≥2 positions avec
    # ≥10 leads qualifiés PROPOSE un REBALANCE humain-approuvé (jamais appliqué
    # seul). NO-OP propre sans bras d'expérience.
    'adsengine-run-reward-divergence-check': {
        'task': 'adsengine.run_reward_divergence_check',
        'schedule': crontab(hour=7, minute=45, day_of_week=1),
    },
    # PUB76 — fraîcheur HEBDO des assets : marque « à revoir » un asset citant
    # une version de FactTable révisée depuis (chiffre périmé à l'antenne) ou une
    # créa saisonnière/expirée. Lundi, heure creuse. NO-OP propre sans asset daté.
    'adsengine-flag-stale-assets': {
        'task': 'adsengine.flag_stale_assets',
        'schedule': crontab(hour=6, minute=50, day_of_week=1),
    },
    # PUB19 — réconciliation QUOTIDIENNE Meta↔ERP (ADSENG31). Après la synchro
    # ENG6 (06:45) : persiste un ReconciliationSnapshot/campagne et alerte 🟠 sur
    # une divergence NOUVELLE au-delà du seuil. NO-OP propre sans campagne.
    'adsengine-run-daily-reconciliation': {
        'task': 'adsengine.run_daily_reconciliation',
        'schedule': crontab(hour=7, minute=55),
    },
    # PUB100 — purge CNDP QUOTIDIENNE des miroirs publicitaires au-delà de leur
    # fenêtre de rétention (MetaLeadMirror/CtwaReferral/InsightBreakdown). Heure
    # creuse ; idempotent ; no-op si fenêtres ≤ 0. Registre de traitement :
    # docs/engine/registre-traitement-cndp.md.
    'adsengine-purge-expired-mirrors': {
        'task': 'adsengine.purge_expired_mirrors',
        'schedule': crontab(hour=3, minute=40),
    },
    # PUB102 — vigie HEBDO de l'EOL de la version Graph API (lundi, heure creuse).
    # Alerte quand la version approche sa fin de vie (~2 ans) ; JAMAIS de bump
    # automatique. No-op tant qu'aucune société active.
    'adsengine-watch-graph-version-eol': {
        'task': 'adsengine.watch_graph_version_eol',
        'schedule': crontab(hour=6, minute=30, day_of_week=1),
    },
    # PUB104 — rollup/archivage MENSUEL des snapshots d'insight (1er du mois,
    # heure creuse). Agrège le détail quotidien au-delà de N mois puis le purge ;
    # totaux additifs conservés dans InsightMonthlyRollup. Idempotent.
    'adsengine-rollup-insights-monthly': {
        'task': 'adsengine.rollup_insights_monthly',
        'schedule': crontab(hour=4, minute=10, day_of_month=1),
    },
    # NTADM11 — purge quotidienne des sandbox expirés (soft puis hard après
    # délai de grâce), 03:05.
    'adminops-purger-sandbox-expires': {
        'task': 'adminops.purger_sandbox_expires',
        'schedule': crontab(hour=3, minute=5),
    },
    # NTADM35 — rappel J-3 / J-48h avant expiration d'un sandbox, 07:35.
    'adminops-rappeler-sandbox-a-expirer': {
        'task': 'adminops.rappeler_sandbox_a_expirer',
        'schedule': crontab(hour=7, minute=35),
    },
    # NTADM36 — recalcul quotidien du health score (historique/tendance), 02:35.
    'adminops-recalculer-health-score-tenants': {
        'task': 'adminops.recalculer_health_score_tenants',
        'schedule': crontab(hour=2, minute=35),
    },
    # NTADM38 — purge mensuelle du contenu des vieux packages de config (1er du
    # mois, 03:35).
    'adminops-purger-config-packages-anciens': {
        'task': 'adminops.purger_config_packages_anciens',
        'schedule': crontab(hour=3, minute=35, day_of_month=1),
    },
    # NTADM16 — purge quotidienne des EvenementUsage au-delà de la rétention
    # configurée (RGPD/CNDP-safe), 03:50.
    'adminops-purger-evenements-usage': {
        'task': 'adminops.purger_evenements_usage',
        'schedule': crontab(hour=3, minute=50),
    },
    # NTADM37 — péremption quotidienne des demandes d'impersonation restées
    # sans consentement au-delà de leur échéance, 03:55. Une demande périmée
    # ne peut jamais être autorisée rétroactivement.
    'adminops-perimer-demandes-impersonation': {
        'task': 'adminops.perimer_demandes_impersonation',
        'schedule': crontab(hour=3, minute=55),
    },
    # ── WIR50 — trois commandes périodiques de SÉCURITÉ/GOUVERNANCE bâties mais
    # jamais planifiées (P0 : elles ne tournaient JAMAIS en prod). ──
    # NTSEC22 — révoque les accès break-glass ÉCHUS (un octroi expiré conserve
    # sinon le rôle Administrateur : élévation de privilège persistante). Cadence
    # rapide (toutes les 10 min) pour rétrograder promptement un accès échu.
    'identity-revoke-expired-break-glass': {
        'task': 'identity.revoke_expired_break_glass',
        'schedule': crontab(minute='*/10'),
    },
    # NTSEC25 — désactive les comptes dormants au-delà du seuil société
    # (balayage par société, notification Directeur préalable). Quotidien.
    # No-op tant qu'aucune société n'a armé de seuil.
    # N4 (décision fondateur 25/09/2026, « aucune notification la nuit ») —
    # déplacée de 02:20 à 08:50 : sa notification « Comptes dormants
    # désactivés » part avec `respect_quiet_hours=False` (alerte de sécurité,
    # jamais reportée par N1), elle tombait donc à 02:20 chez le Directeur.
    # Un compte dormant l'est depuis des jours : le désactiver à 08:50 plutôt
    # qu'à 02:20 ne change rien à la sécurité, et le Directeur est prévenu aux
    # heures de travail.
    'authentication-desactiver-comptes-dormants': {
        'task': 'authentication.desactiver_comptes_dormants',
        'schedule': crontab(hour=8, minute=50),
    },
    # NTDMO30 — purge hebdomadaire des sociétés démo TAQINOR expirées
    # (staging/marketing uniquement). No-op tant que
    # DEMO_AUTO_PURGE_ENABLED=0 (défaut) — le founder l'active explicitement.
    'authentication-purger-societes-demo-expirees': {
        'task': 'authentication.purger_societes_demo_expirees',
        'schedule': crontab(hour=3, minute=45, day_of_week=1),
    },
    # FG366 — escalade les étapes de workflow au SLA dépassé (balayage par
    # société, WorkflowStepInstance en attente échue). Horaire.
    'core-escalate-workflow-sla': {
        'task': 'core.escalate_workflow_sla',
        'schedule': crontab(minute=20),
    },
    # NTDATA26 — exécute les extraits planifiés DUS (`ScheduledExport.cron`).
    # HORAIRE : le grain de planification des extraits EST l'heure (le champ
    # minute du cron est accepté puis ignoré, comme pour les abonnements de
    # rapport). Idempotent : un extrait déjà passé dans l'heure courante n'est
    # jamais renvoyé. Destination non configurée = no-op propre horodaté.
    'core-executer-exports-planifies': {
        'task': 'core.executer_exports_planifies',
        'schedule': crontab(minute=35),
    },
    # WIR73 (GED7) — planifie `migrate_attachments_to_ged` en récurrent :
    # sans cette entrée, une pièce jointe créée après le dernier import MANUEL
    # n'apparaissait jamais en GED (la commande existait, testée, mais rien ne
    # l'exécutait). Hebdomadaire (lundi, heure creuse) — idempotente (clé
    # company + file_key), rejouer ne duplique jamais un document déjà importé.
    'ged-migrer-pieces-jointes-hebdo': {
        'task': 'ged.migrer_pieces_jointes',
        'schedule': crontab(hour=3, minute=25, day_of_week=1),
    },
    # NTUX29 — purge quotidienne de rétention de la corbeille transverse (30 j,
    # NTUX7) : la commande `purger_corbeille_transverse` était bâtie mais
    # jamais planifiée (bug dominant du repo : une tâche testée mais absente
    # du beat ne tourne jamais). Heure creuse.
    'trash-purger-corbeille-transverse': {
        'task': 'trash.purger_corbeille_transverse',
        'schedule': crontab(hour=3, minute=0),
    },
    # NTUX30 — digest HEBDOMADAIRE (lundi 07h00) des favoris/vues pointant vers
    # une cible définitivement supprimée (ex. purgée de la corbeille ci-dessus).
    # Notifie le propriétaire, ne supprime jamais rien automatiquement.
    'uxviews-digest-favoris-obsoletes-hebdo': {
        'task': 'uxviews.digest_favoris_obsoletes_hebdo',
        'schedule': crontab(hour=7, minute=0, day_of_week=1),
    },
    # ── AUD231 — huit balayages écrits « pour Celery beat » et planifiés NULLE
    # PART. Chacune de ces commandes de gestion l'annonçait dans sa docstring
    # (« Plannifiable par Celery beat », « cron / Celery beat », « Sweep
    # quotidien … (Celery beat) ») alors que le grep sur `erp_agentique/`
    # rendait ZÉRO : elles ne tournaient que si quelqu'un les lançait à la
    # main. Conséquence la plus visible : une réservation Click & Collect
    # expirée n'était JAMAIS libérée, son stock restant réservé indéfiniment.
    # La garde `scripts/check_commandes_planifiees.py` empêche désormais la
    # récidive sur TOUTES les apps.

    # NTWMS13 — sessions d'inventaire de comptage tournant dues (idempotent :
    # rejoué le même jour, ne recrée rien). Heure creuse, avant le bloc stock.
    'stock-generer-comptages-tournants': {
        'task': 'stock.generer_comptages_tournants',
        'schedule': crontab(hour=5, minute=15),
    },
    # NTWMS12 — libération des vagues de prélèvement AUTO_HEURE / AUTO_SEUIL.
    # Cadence courte ASSUMÉE : l'heure de coupure est un réglage PAR SOCIÉTÉ
    # (`AchatsParametres.heure_coupure_vagues`), à la minute près — un job
    # quotidien laisserait une vague attendre jusqu'au lendemain. Requête
    # bornée aux vagues BROUILLON non manuelles, donc vide la plupart du temps.
    'stock-liberer-vagues-planifiees': {
        'task': 'stock.liberer_vagues_planifiees',
        'schedule': crontab(minute='*/15'),
    },
    # ZFSM3 — prochaine intervention de chaque récurrence active à échéance
    # (prestation périodique SANS contrat de maintenance). Idempotent.
    'installations-generer-interventions-recurrentes': {
        'task': 'installations.generer_interventions_recurrentes',
        'schedule': crontab(hour=5, minute=35),
    },
    # NTOBS1 — rafraîchit les composants publics de la page de statut depuis
    # `core.health.check_services()` (best-effort, jamais bloquant). Toutes
    # les 5 minutes — la Done criteria de NTOBS1 exige qu'un composant marqué
    # `degraded` apparaisse publiquement en ≤5 min.
    'statuspage-rafraichir-composants': {
        'task': 'statuspage.rafraichir_composants',
        'schedule': crontab(minute='*/5'),
    },
    # NTOBS3 — snapshot SLA mensuel (uptime + P95) de toutes les sociétés,
    # le 1er du mois (le mois qui vient de se terminer).
    'core-generer-sla-mensuel': {
        'task': 'core.generer_sla_mensuel',
        'schedule': crontab(day_of_month=1, hour=3, minute=15),
    },
    # NTOBS9 — notifie 24h/1h avant une fenêtre de maintenance planifiée.
    'core-notifier-fenetres-maintenance': {
        'task': 'core.notifier_fenetres_maintenance',
        'schedule': crontab(minute='*/15'),
    },
    # NTOBS13 — notifie chaque société franchissant 80%/100% d'un quota mesuré.
    'core-notifier-seuils-usage': {
        'task': 'core.notifier_seuils_usage',
        'schedule': crontab(hour=7, minute=10),
    },
    # NTOBS24 — purge GFS mensuelle des vieilles données Fiabilité (incidents
    # résolus >2 ans, exports de réversibilité expirés >30j, buckets d'uptime
    # >400j).
    'core-purger-donnees-fiabilite': {
        'task': 'core.purger_donnees_fiabilite',
        'schedule': crontab(day_of_month=1, hour=4, minute=0),
    },
    # NTWFL17 — balayage quotidien des échéances de dossier dépassées, par
    # société active (dédup anti-spam déjà dans le modèle Dossier).
    'core-notifier-dossiers-echeance-depassee': {
        'task': 'core.notifier_dossiers_echeance_depassee',
        'schedule': crontab(hour=7, minute=5),
    },
    # NTOBS25 — recalcul quotidien des SlaSnapshot périmés par un incident
    # déclaré/modifié tardivement (chevauchant une période déjà générée).
    'core-recalculer-sla-perimes': {
        'task': 'core.recalculer_sla_perimes',
        'schedule': crontab(hour=3, minute=45),
    },
    # NTOBS34 — alerte fondateur si un audit TrustCenterEntry a plus de 12 mois.
    'core-verifier-fraicheur-trust-center': {
        'task': 'core.verifier_fraicheur_trust_center',
        'schedule': crontab(hour=6, minute=30),
    },
    # NTI18N39 — recalcul HEBDOMADAIRE de la couverture i18n (NTI18N28), le
    # lundi tôt : l'instantané de la semaine est prêt avant la journée de
    # travail, et la clé d'idempotence (société, lundi de la semaine) rend un
    # rejeu inoffensif.
    'core-recalculer-couverture-i18n': {
        'task': 'core.recalculer_couverture_i18n',
        'schedule': crontab(day_of_week=1, hour=5, minute=20),
    },
    # NTOBS31 — garantit, pour chaque société active, les 2 KpiAlerte par
    # défaut (drill de restauration périmé > 35 j, quota saturé >= 100 %)
    # AVANT le beat d'évaluation ci-dessus (6h30) qui les calcule/notifie.
    'core-assurer-alertes-fiabilite-kpi': {
        'task': 'core.assurer_alertes_fiabilite_kpi',
        'schedule': crontab(hour=6, minute=0),
    },
    # NTI18N38 — purge MENSUELLE des traductions de contenu orphelines
    # (`core.ContentTranslation` désigne sa cible par contenttype+object_id,
    # donc la suppression de l'objet source n'emporte rien). Le 1er du mois,
    # heure creuse — voir apps/parametres/scheduled.py.
    'parametres-purger-traductions-orphelines': {
        'task': 'parametres.purger_traductions_orphelines',
        'schedule': crontab(day_of_month=1, hour=4, minute=20),
    },
    # NTI18N51 — UNE notification groupée par société des clés de glossaire qui
    # ont replié sur le français en production. Le lundi matin : la lacune est
    # lue avant la semaine de travail, et l'hebdomadaire est ce qui rend
    # l'alerte anti-spam (le compteur, lui, tourne en continu).
    'parametres-notifier-traductions-manquantes-hebdo': {
        'task': 'parametres.notifier_traductions_manquantes_hebdo',
        'schedule': crontab(day_of_week=1, hour=7, minute=35),
    },
}

# YHARD6 — compteurs Celery succès/échec (process-local, best-effort) pour
# l'endpoint /metrics. Enregistrés au niveau du signal Celery (pas Django) :
# fonctionne aussi bien côté worker que côté beat, sans importer d'app métier.
from celery.signals import task_success, task_failure  # noqa: E402


def _queue_of(sender):
    """NTPLT44 — nom de queue best-effort d'une tâche (routing_key), 'default'."""
    try:
        info = getattr(getattr(sender, 'request', None), 'delivery_info', None)
        return (info or {}).get('routing_key') or 'default'
    except Exception:  # noqa: BLE001 — best-effort
        return 'default'


@task_success.connect
def _yhard6_on_task_success(sender=None, **kwargs):
    try:
        from core import metrics
        metrics.record_task_success()
        metrics.record_task_queue(_queue_of(sender), ok=True)  # NTPLT44
    except Exception:  # noqa: BLE001 — best-effort, ne doit jamais casser Celery
        pass


@task_failure.connect
def _yhard6_on_task_failure(sender=None, **kwargs):
    try:
        from core import metrics
        metrics.record_task_failure()
        metrics.record_task_queue(_queue_of(sender), ok=False)  # NTPLT44
    except Exception:  # noqa: BLE001 — best-effort, ne doit jamais casser Celery
        pass
