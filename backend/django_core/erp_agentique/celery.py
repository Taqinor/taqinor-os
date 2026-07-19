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
app.conf.beat_schedule = {
    'ventes-check-overdue-factures': {
        'task': 'ventes.check_overdue_factures',
        'schedule': crontab(hour=0, minute=30),
    },
    # NTTRE29/31 — trésorerie : alerte rupture (quotidien) + relances du jour.
    'compta-recalculer-alerte-rupture': {
        'task': 'compta.recalculer_alerte_rupture',
        'schedule': crontab(hour=6, minute=45),
    },
    'compta-relances-tresorerie-du-jour': {
        'task': 'compta.relances_tresorerie_du_jour',
        'schedule': crontab(hour=7, minute=5),
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
    # VX210 — réveille les items snoozés (activités + approbations) dont
    # l'échéance de snooze est passée ; toutes les 30 min pour un réveil prompt.
    'notifications-reveiller-snoozes': {
        'task': 'notifications.reveiller_snoozes',
        'schedule': crontab(minute='*/30'),
    },
    # VX209(c) — purge/archive quotidienne des notifications anciennes (lues
    # > 60 j supprimées, non-lues > 60 j archivées) ; heure creuse.
    'notifications-purge-anciennes': {
        'task': 'notifications.purge_notifications_anciennes',
        'schedule': crontab(hour=2, minute=45),
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
    # ZGED14 — notifie les ÉMETTEURS de demandes de signature dont
    # l'expiration approche (versant émetteur, complète XGED2 ci-dessus).
    'ged-notifier-emetteurs-expiration-signature': {
        'task': 'ged.notifier_emetteurs_expiration_signature',
        'schedule': crontab(hour=8, minute=0),
    },
    'crm-recycler-leads-non-travailles': {
        'task': 'crm.recycler_leads_non_travailles',
        'schedule': crontab(minute=0),  # every hour
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
    # NTSUB5 — conversion des essais d'abonnement échus + alerte J-3,
    # quotidien (heure creuse).
    'contrats-convertir-essais-expires-daily': {
        'task': 'contrats.convertir_essais_expires_daily',
        'schedule': crontab(hour=2, minute=30),
    },
    # NTSUB8 — séquences de dunning (relances impayés multi-étapes),
    # quotidien.
    'contrats-executer-dunning-daily': {
        'task': 'contrats.executer_dunning_daily',
        'schedule': crontab(hour=8, minute=0),
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
    # XFSM6 — rappel client J-1 (interventions non confirmées, demain).
    'installations-rappel-rdv-j1': {
        'task': 'installations.rappel_rdv_j1',
        'schedule': crontab(hour=7, minute=45),
    },
    # YHIRE8 — alertes d'expiration RH (habilitations/certifs/docs/visites/
    # EPI), quotidien, heure creuse matinale.
    'rh-alertes-expiration': {
        'task': 'rh.alertes_expiration',
        'schedule': crontab(hour=7, minute=50),
    },
    # YHIRE8 — alerte fin de CDD (J-30 par défaut), quotidien.
    'rh-alertes-cdd': {
        'task': 'rh.alertes_cdd',
        'schedule': crontab(hour=7, minute=55),
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
    # (planifiée séparément par NTSRV38). OFF par défaut par société
    # (sla_warning_days=0, escalade_activee=False) : no-op tant qu'aucun
    # réglage n'est activé.
    'sav-scan-sla-pre-alerts-and-escalations': {
        'task': 'sav.scan_sla_pre_alerts_and_escalations_quotidien',
        'schedule': crontab(hour=7, minute=42),
    },
    # XFSM21 — météo J+3 sur les poses planifiées (Open-Meteo, gratuit,
    # sans clé), quotidien, heure creuse matinale.
    'installations-meteo-planning-j3': {
        'task': 'installations.meteo_planning_j3',
        'schedule': crontab(hour=6, minute=30),
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
    # XMKT1 — exécute les étapes de séquences de relance marketing dues.
    'compta-executer-sequences-relance': {
        'task': 'compta.executer_sequences_relance',
        'schedule': crontab(hour=8, minute=10),
    },
    # XMKT7 — envoie les campagnes marketing planifiées dues.
    'compta-envoyer-campagnes-planifiees': {
        'task': 'compta.envoyer_campagnes_planifiees',
        'schedule': crontab(minute='*/15'),
    },
    # XMKT — communications d'événement dues (anniversaires/jalons).
    'compta-envoyer-communications-evenement': {
        'task': 'compta.envoyer_communications_evenement',
        'schedule': crontab(hour=8, minute=20),
    },
    # XMKT — recalcule les contacts marketing dormants, quotidien.
    'compta-recalculer-dormants-marketing': {
        'task': 'compta.recalculer_dormants_marketing',
        'schedule': crontab(hour=3, minute=40),
    },
    # XMKT — publie les posts sociaux programmés dus.
    'compta-traiter-posts-sociaux': {
        'task': 'compta.traiter_posts_sociaux',
        'schedule': crontab(minute='*/15'),
    },
    # XMKT — décide les gagnants des tests A/B arrivés à terme.
    'compta-decider-gagnants-ab': {
        'task': 'compta.decider_gagnants_ab',
        'schedule': crontab(hour=8, minute=25),
    },
    # XKB7 — relance quotidienne des non-lecteurs de lecture obligatoire.
    'kb-sweep-lectures-obligatoires': {
        'task': 'kb.sweep_lectures_obligatoires',
        'schedule': crontab(hour=8, minute=30),
    },
    # XKB14 — relance de re-revue des articles KB périmés, quotidien.
    'kb-sweep-articles-perimes': {
        'task': 'kb.sweep_articles_perimes',
        'schedule': crontab(hour=8, minute=35),
    },
    # XFSM24 — escalade des check-ins QHSE en retard.
    'qhse-escalader-checkins-en-retard': {
        'task': 'qhse.escalader_checkins_en_retard',
        'schedule': crontab(minute='*/30'),
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
    # NTCRD21 — alerte quotidienne d'exposition crédit consolidée (07:20).
    # Best-effort, une alerte par jour et par société (dédup), no-op tant que
    # le seuil société vaut 0 (défaut).
    'credit-alerter-exposition-globale': {
        'task': 'credit.alerter_exposition_globale',
        'schedule': crontab(hour=7, minute=20),
    },
    # NTCRD33 — expiration quotidienne des dérogations crédit échues (01:15).
    'credit-expirer-derogations': {
        'task': 'credit.expirer_derogations',
        'schedule': crontab(hour=1, minute=15),
    },
    # NTCRD34 — alerte hebdomadaire (lundi 07:25) des polices d'assurance-crédit
    # proches de leur échéance (J-30).
    'credit-alerter-polices-expirantes': {
        'task': 'credit.alerter_polices_expirantes',
        'schedule': crontab(hour=7, minute=25, day_of_week=1),
    },
    # NTCRD32 — rafraîchit le cache court d'encours (quotidien, 02:10).
    'credit-recalculer-encours-quotidien': {
        'task': 'credit.recalculer_encours_quotidien',
        'schedule': crontab(hour=2, minute=10),
    },
    # NTSAN31 — alerte J-7 avant expiration d'une PriseEnCharge santé (évite
    # les actes réalisés hors couverture), quotidien, heure creuse matinale.
    'sante-alertes-prise-en-charge-expirant': {
        'task': 'sante.alertes_prise_en_charge_expirant',
        'schedule': crontab(hour=7, minute=40),
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
    # NTEDU22 — matérialise les séances de la semaine à venir depuis l'emploi
    # du temps actif. Dimanche soir (heure creuse), avant la semaine ciblée.
    'education-generer-seances-semaine': {
        'task': 'education.generer_seances_semaine',
        'schedule': crontab(hour=20, minute=0, day_of_week=0),
    },
    # NTIDE40 — digest feedback produit non-lu par thème, gated PAR SOCIÉTÉ
    # (InnovationSettings.feedback_digest_actif), quotidien (heure creuse
    # matinale, la fréquence hebdo interne ne notifie que le lundi).
    'innovation-feedback-digest': {
        'task': 'innovation.feedback_digest_run',
        'schedule': crontab(hour=8, minute=40),
    },
    # NTEDU40 — relance réinscription (élèves sans Inscription pour l'année
    # suivante après la date limite paramétrable) : quotidien, heure creuse.
    'education-relancer-reinscriptions': {
        'task': 'education.relancer_reinscriptions',
        'schedule': crontab(hour=7, minute=50),
    },
    # WIR5/FLOTTE16 — génère réellement les échéances d'entretien flotte
    # (avant cette entrée : ni beat ni bouton, seule la commande manage
    # fonctionnait — l'onglet Échéances et le KPI « entretien » du Cockpit
    # Flotte restaient silencieusement vides). Quotidien, heure creuse.
    'flotte-generer-echeances-entretien-quotidien': {
        'task': 'flotte.generer_echeances_entretien_quotidien',
        'schedule': crontab(hour=6, minute=45),
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
    # (balayage par société, notification Directeur préalable). Quotidien,
    # heure creuse. No-op tant qu'aucune société n'a armé de seuil.
    'authentication-desactiver-comptes-dormants': {
        'task': 'authentication.desactiver_comptes_dormants',
        'schedule': crontab(hour=2, minute=20),
    },
    # FG366 — escalade les étapes de workflow au SLA dépassé (balayage par
    # société, WorkflowStepInstance en attente échue). Horaire.
    'core-escalate-workflow-sla': {
        'task': 'core.escalate_workflow_sla',
        'schedule': crontab(minute=20),
    },
    # WIR25 (XACC8) — génère les écritures dues des abonnements récurrents
    # (loyers/abonnements) en brouillon, quotidien, heure creuse. Idempotent
    # par période (rejouer le même jour ne crée rien) ; no-op sans abonnement.
    'compta-generer-ecritures-recurrentes': {
        'task': 'compta.generer_ecritures_recurrentes',
        'schedule': crontab(hour=2, minute=15),
    },
    # WIR25 (NTMAR15) — rappels d'échéance fiscale (CNSS/taxe pro/TVA/IS…)
    # N jours avant la date limite, quotidien, heure creuse matinale.
    # Idempotent via rappel_envoye_le (pas de double envoi le même jour).
    'fiscal-rappels-fiscaux': {
        'task': 'fiscal.rappels_fiscaux',
        'schedule': crontab(hour=6, minute=40),
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
