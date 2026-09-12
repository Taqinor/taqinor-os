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
#   - WIR73 : import GED hebdomadaire des pièces jointes éparses (idempotent,
#     lundi 03:25) — apps/ged/tasks.py (`migrate_attachments_to_ged`, GED7).
#   - WIR148 : génération quotidienne de l'échéancier de loyer des baux actifs
#     (idempotent, 02:38) — apps/immobilier/tasks.py.
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
    # AOF15 — rappels d'échéances d'appel d'offres (remise des plis, ouverture,
    # fin de validité). Un dossier d'AO se perd sur une date, jamais sur la
    # technique : passage quotidien tôt, avant la journée de travail.
    # AUD614 — la GÉNÉRATION de l'échéancier passe AVANT son rappel. Elle
    # n'était dispatchée nulle part : `ao.rappeler_echeances` rappelait donc un
    # échéancier qui n'existait pas — un no-op silencieux, la pire forme de
    # panne (l'écran « Tâches planifiées » affichait vert). Générer APRÈS le
    # rappel aurait fait attendre un jour à chaque nouvelle échéance.
    'ao-generer-echeanciers': {
        'task': 'ao.generer_echeanciers',
        'schedule': crontab(hour=6, minute=15),
    },
    'ao-rappeler-echeances': {
        'task': 'ao.rappeler_echeances',
        'schedule': crontab(hour=6, minute=30),
    },
    # AUD614 — relance PROACTIVE des pièces administratives qui vont expirer.
    # Elle n'existait qu'en action GET : il fallait ALLER VOIR pour apprendre
    # qu'une attestation expire, alors qu'une attestation périmée le jour de
    # l'ouverture fait ÉCARTER le pli. Après les échéances (l'ordre du matin
    # va du plus daté au plus administratif) ; cadencée à une relance par
    # pièce tous les 7 jours (voir `ao/scheduled.py`).
    'ao-relancer-pieces-administratives': {
        'task': 'ao.relancer_pieces_administratives',
        'schedule': crontab(hour=6, minute=45),
    },
    # AUD614 — expiration des avis dont la date limite est passée. Le service
    # existait, testé, et n'était appelé par AUCUN chemin de production : un
    # avis dont la remise est passée restait « nouveau » indéfiniment, et le
    # tri humain se faisait sur une liste polluée. AUCUN appel réseau (règle
    # #5) : la tâche compare une date déjà en base à l'horloge — elle n'est
    # donc pas gardée par VEILLE_AO_COLLECTE_ACTIVE, qui arme l'ACQUISITION.
    # Juste après la collecte de 06:00, pour nettoyer ce qu'elle vient de voir.
    'veille-ao-expirer-avis-depasses': {
        'task': 'veille_ao.expirer_avis_depasses',
        'schedule': crontab(hour=6, minute=10),
    },
    # VAO22 — veille appels d'offres, collecte du matin. 06:00 parce que les
    # remises de plis sont à 10 h-11 h : l'information du matin est
    # actionnable LE JOUR MÊME. L'entrée est présente et la tâche est
    # INERTE tant que VEILLE_AO_COLLECTE_ACTIVE vaut 0 (le défaut) — l'acte
    # d'armement est une décision fondateur datée (règle #5, VAO4), jamais
    # celle d'un agent. Planifier la tâche désarmée est délibéré : une tâche
    # absente du beat est le mode de défaillance dominant du dépôt (bâtie,
    # testée, jamais exécutée).
    'veille-ao-collecte-quotidienne': {
        'task': 'veille_ao.collecte_quotidienne',
        'schedule': crontab(hour=6, minute=0),
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
    # NTDATA15 — évalue les règles de qualité de données de chaque société
    # opérationnelle et journalise un ResultatQualite daté. Placé AVANT les
    # alertes KPI : le rapport de qualité du matin est déjà à jour quand la
    # direction l'ouvre. Lecture seule côté métier — ne corrige rien.
    'dataquality-evaluer-qualite-donnees': {
        'task': 'dataquality.evaluer_qualite_donnees',
        'schedule': crontab(hour=5, minute=45),
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
    # NTDATA24 — recalcule les golden records (fiches consolidées) de chaque
    # société. HEBDOMADAIRE : la passe relit toutes les fiches des trois
    # entités et rejoue la détection de doublons, et l'identité consolidée d'un
    # client ne change pas d'un jour à l'autre. Dimanche très tôt (créneau
    # creux, avant la semaine) ; aucune source n'est mutée — c'est une VUE.
    'dataquality-consolider-golden-records': {
        'task': 'dataquality.consolider_golden_records',
        'schedule': crontab(hour=4, minute=15, day_of_week=0),
    },
    # YSERV13 — contrôle d'intégrité inter-documents hebdomadaire (états
    # orphelins entre apps) ; notifie seulement si ≥1 anomalie détectée.
    'reporting-controle-integrite-hebdo': {
        'task': 'reporting.controle_integrite',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),
    },
    # NTGRC34 — rappels d'échéances GRC (DSR, violations 72 h, revues de
    # risque, contrôles à tester, politiques non attestées). Quotidien, tôt :
    # le DPO doit voir ses échéances AVANT sa journée, pas après. Idempotent
    # (une notification par échéance et par jour), donc un double tick ne
    # produit jamais de doublon.
    'grc-rappels-echeances': {
        'task': 'grc.rappels_grc',
        'schedule': crontab(hour=6, minute=30),
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
    # AUD524 (ZCTR2) — suspension des contrats impayes. Le service existait,
    # la management command aussi, et `contrats/scheduled.py` renvoyait deja au
    # « beat cloturer_contrats_impayes separe » — qui n'existait pas. Un
    # contrat sans sequence de dunning n'etait donc JAMAIS suspendu
    # automatiquement. Heure creuse, juste apres le dunning.
    'contrats-cloturer-impayes-daily': {
        'task': 'contrats.cloturer_contrats_impayes_daily',
        'schedule': crontab(hour=8, minute=20),
    },
    # NTDOC32 — purge des dépôts « contrepartie » ARCHIVÉS dont la durée de
    # rétention configurée (politique GED de la société) est dépassée.
    # Quotidien, heure creuse. Sans politique applicable, la tâche ne purge
    # RIEN (jamais de durée codée en dur).
    'contrats-purger-contreparties-archivees': {
        'task': 'contrats.purger_contreparties_archivees',
        'schedule': crontab(hour=2, minute=45),
    },
    # NTSUB27 — précalcul NOCTURNE des métriques SaaS du cockpit (ARR bridge /
    # Quick Ratio / Rule of 40). Le cockpit retombe seul sur le calcul à la
    # volée si ce job n'a pas tourné : aucune dépendance dure.
    'contrats-recalculer-metriques-saas-cache-daily': {
        'task': 'contrats.recalculer_metriques_saas_cache_daily',
        'schedule': crontab(hour=1, minute=50),
    },
    # NTSUB26 — purge MENSUELLE des relevés d'usage bruts d'une période DÉJÀ
    # FACTURÉE et vieille de plus de 24 mois (agrégés d'abord en une ligne de
    # synthèse). Le 1er du mois, heure creuse.
    'contrats-purger-compteurs-usage-factures-monthly': {
        'task': 'contrats.purger_compteurs_usage_factures_monthly',
        'schedule': crontab(hour=3, minute=40, day_of_month=1),
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
    # AUD730 — acquisition mensuelle des congés payés (ZRH2, « Accrual Time
    # Off » Odoo) : le 1er de chaque mois, heure creuse. Idempotent (garde
    # ``mois_acquis``) — une double exécution ne crédite jamais deux fois.
    'rh-accruer-conges-mensuel': {
        'task': 'rh.accruer_conges',
        'schedule': crontab(hour=1, minute=30, day_of_month=1),
    },
    # AUD730 — clôture automatique des pointages restés ouverts (ZRH5,
    # « Automatic check-out » Odoo), quotidien en fin de nuit. No-op tant
    # qu'aucune société n'a configuré son seuil.
    'rh-clore-pointages-ouverts': {
        'task': 'rh.clore_pointages_ouverts',
        'schedule': crontab(hour=3, minute=20),
    },
    # AUD730 — rétention CNDP des candidatures rejetées (XRH24), quotidien.
    # DRY-RUN tant que RH_PURGE_CANDIDATURES_AUTO_APPLY n'est pas posé
    # (anonymisation irréversible) — la tâche SIGNALE alors le volume éligible.
    'rh-purger-candidatures': {
        'task': 'rh.purger_candidatures',
        'schedule': crontab(hour=3, minute=40),
    },
    # AUD730 — planification des appréciations dues (ZRH8), hebdomadaire (lundi).
    # DRY-RUN tant que RH_APPRECIATIONS_AUTO_APPLY n'est pas posé : la cadence
    # d'un cycle d'appréciation est une décision métier du fondateur.
    'rh-planifier-appreciations': {
        'task': 'rh.planifier_appreciations',
        'schedule': crontab(hour=4, minute=10, day_of_week=1),
    },
    # NTHCM19 — relance des parcours de formation OBLIGATOIRES non terminés
    # au-delà du délai société (ReglageRH.rappel_parcours_apres_jours, défaut
    # 14 j), quotidien. Dédoublonné par jour et par parcours : deux passages
    # le même jour ne relancent jamais deux fois la même personne.
    'rh-rappels-parcours-formation': {
        'task': 'rh.rappels_parcours_formation',
        'schedule': crontab(hour=8, minute=10),
    },
    # NTHCM25 — rappel quotidien des tâches d'intégration/sortie ASSIGNÉES et
    # echues (la revocation d'acces IT en tete des risques). Dedoublonne par
    # jour et par tache : deux passages le meme jour ne relancent jamais deux
    # fois le meme acteur.
    'rh-notifier-taches-integration-sortie': {
        'task': 'rh.notifier_taches_integration_sortie',
        'schedule': crontab(hour=8, minute=20),
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
    # NTMKT12 — tick des séquences EN GRAPHE (journeys) : complément strict du
    # tick linéaire XMKT1 ci-dessus, décalé de 5 min pour ne pas les superposer.
    'marketing-executer-journeys': {
        'task': 'marketing.executer_journeys',
        'schedule': crontab(hour=8, minute=15),
    },
    # NTMKT33 — purge quotidienne des jetons publics marketing expirés (+90j).
    'marketing-purger-tokens-expires': {
        'task': 'marketing.purger_tokens_expires',
        'schedule': crontab(hour=3, minute=0),
    },
    # NTMKT35 — rappel d'approbation d'envoi de campagne en attente (+24h).
    'marketing-rappeler-approbations-envoi': {
        'task': 'marketing.rappeler_approbations_envoi',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    # NTMKT34 — recalcul quotidien du score de maturité (pénalité inactivité
    # 30j) — no-op pour une société qui n'a jamais activé NTMKT18.
    'marketing-recalculer-scores-maturite-inactivite': {
        'task': 'marketing.recalculer_scores_maturite_inactivite',
        'schedule': crontab(hour=4, minute=0),
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
    # PACT184 (XQHS12) — rappel légal de réunion CSH trimestrielle (Code du
    # travail, ≥50 salariés). ``csh_relance_due`` était testé mais sans
    # aucun appelant : la relance restait invisible même cadence dépassée.
    # Quotidien, heure creuse (dédup au jour via Notification).
    'qhse-relancer-csh-du-jour': {
        'task': 'qhse.relancer_csh_du_jour',
        'schedule': crontab(hour=7, minute=48),
    },
    # AUD524 (XQHS2) — relance des derogations a echeance. Le service etait
    # teste et correct, mais n'avait AUCUN appelant hors tests : une derogation
    # arrivant a echeance n'etait jamais relancee. Quotidien, heure creuse.
    'qhse-relancer-derogations': {
        'task': 'qhse.relancer_derogations',
        'schedule': crontab(hour=7, minute=52),
    },
    # AUD524 (XQHS10) — audits planifies dont la date cible est depassee. Meme
    # constat : service teste, zero appelant, aucun passage automatique en
    # « en_retard ». Quotidien, heure creuse.
    'qhse-relancer-audits-planifies-en-retard': {
        'task': 'qhse.relancer_audits_planifies_en_retard',
        'schedule': crontab(hour=7, minute=56),
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
    # NTMIG35 — purge quotidienne des fichiers source de migration (PII)
    # des projets clôturés depuis plus de 30 jours, 02:50.
    'migration-purger-fichiers': {
        'task': 'migration.purger_fichiers_migration',
        'schedule': crontab(hour=2, minute=50),
    },
    # NTMIG30 — alerte quotidienne J-60 avant expiration d'une certification
    # partenaire (crm.Partenaire), 07:35.
    'migration-alerter-certifications-expirantes': {
        'task': 'migration.alerter_certifications_expirantes',
        'schedule': crontab(hour=7, minute=35),
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
    # AUD725 — matérialise le coût récurrent DU MOIS des contrats véhicule
    # (leasing/LLD/location) dans le grand livre unifié : avant cette
    # entrée, ni beat ni bouton, seule la commande manage fonctionnait ET
    # écrivait dans un modèle jamais exposé (ni Cockpit Flotte, ni
    # ledger/TCO). Mensuel, 1er du mois, heure creuse.
    'flotte-generer-couts-contrat-mensuel': {
        'task': 'flotte.generer_couts_contrat_mensuel',
        'schedule': crontab(hour=6, minute=47, day_of_month=1),
    },
    # NTLOG38 — rappel J-3 sur les étapes de transport en retard
    # (`date_prevue` dépassée, jamais clôturées) : quotidien, heure creuse,
    # idempotent (une seule notification par étape par jour).
    'transport-check-etapes-retard-quotidien': {
        'task': 'transport.check_etapes_transport_retard',
        'schedule': crontab(hour=6, minute=50),
    },
    # NTLOG39 — archivage (jamais suppression) des ordres de transport livrés
    # depuis plus de N mois (défaut 24, `ParametresTransport.
    # archive_ordres_apres_mois`) : mensuel, 1er du mois, heure creuse.
    'transport-archiver-ordres-anciens-mensuel': {
        'task': 'transport.archiver_ordres_transport_anciens',
        'schedule': crontab(hour=3, minute=10, day_of_month=1),
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
    # WIR73 (GED7) — planifie `migrate_attachments_to_ged` en récurrent :
    # sans cette entrée, une pièce jointe créée après le dernier import MANUEL
    # n'apparaissait jamais en GED (la commande existait, testée, mais rien ne
    # l'exécutait). Hebdomadaire (lundi, heure creuse) — idempotente (clé
    # company + file_key), rejouer ne duplique jamais un document déjà importé.
    'ged-migrer-pieces-jointes-hebdo': {
        'task': 'ged.migrer_pieces_jointes',
        'schedule': crontab(hour=3, minute=25, day_of_week=1),
    },
    # WIR148 (NTPRO6) — génère réellement les `EcheanceLoyer` des baux actifs :
    # avant cette entrée, seule la commande manage `generer_echeances_loyer`
    # fonctionnait (jamais exécutée automatiquement) — l'échéancier restait
    # silencieusement vide sans relance manuelle. Quotidien, heure creuse ;
    # idempotent (unique_together bail + periode_debut).
    'immobilier-generer-echeances-loyer-quotidien': {
        'task': 'immobilier.generer_echeances_loyer',
        'schedule': crontab(hour=2, minute=38),
    },
    # NTAI29 — surveillance MENSUELLE de la dérive (PSI) des features d'entrée
    # des scorers, par société. Pur/offline (stats stdlib, aucun appel LLM) et
    # no-op propre tant qu'aucun fournisseur de distribution n'est déclaré.
    # 1er du mois, heure creuse.
    'ai-governance-surveiller-drift-mensuel': {
        'task': 'ai_governance.surveiller_drift_mensuel',
        'schedule': crontab(hour=4, minute=25, day_of_month=1),
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
    # NTCPQ32 — rappel quotidien (activité, jamais d'email auto) des
    # PrixContractuel dont date_fin est dépassée — apps/cpq/scheduled.py.
    # Idempotent (une seule activité par prix expiré). Heure creuse.
    'cpq-expire-prix-contractuels': {
        'task': 'cpq.expire_prix_contractuels',
        'schedule': crontab(hour=4, minute=40),
    },
    # NTCPQ33 — relance les EtapeApprobationDevis en_attente depuis plus de
    # N jours (ParametresCPQ.delai_relance_approbation_jours) — apps/cpq/
    # scheduled.py. Idempotent (max 1 relance/24h/étape).
    'cpq-relancer-approbations-en-attente': {
        'task': 'cpq.relancer_approbations_en_attente',
        'schedule': crontab(hour=7, minute=20),
    },
    # NTCPQ34 — purge les SessionConfigurateur inactives >30j sans devis lié
    # — apps/cpq/scheduled.py. Additive-safe (aucune session ayant abouti à
    # un devis, même brouillon, n'est jamais touchée).
    'cpq-purger-sessions-configurateur-abandonnees': {
        'task': 'cpq.purger_sessions_configurateur_abandonnees',
        'schedule': crontab(hour=3, minute=50),
    },
    # NTSCM21 — (re)génère les prévisions de demande (NTSCM2) de tous les
    # produits actifs, pour chaque société, le 1er de chaque mois — apps/scm/
    # tasks.py. Best-effort par société ET par produit ; notifie un résumé.
    'scm-generer-previsions-mensuelles': {
        'task': 'scm.generer_previsions_mensuelles',
        'schedule': crontab(hour=5, minute=10, day_of_month=1),
    },
    # NTSCM22 — ouvre le CyclePlanificationSOP du mois suivant (brouillon)
    # le 20 de chaque mois, UNIQUEMENT pour les sociétés opt-in
    # (`ParametresSCM.sop_actif`, défaut désactivé) — apps/scm/tasks.py.
    'scm-ouvrir-cycle-sop-mensuel': {
        'task': 'scm.ouvrir_cycle_sop_mensuel',
        'schedule': crontab(hour=5, minute=30, day_of_month=20),
    },
    # NTMFG30 — recalcul MRP nocturne (NTMFG5) + notification des ruptures
    # prévisionnelles sur l'horizon `ParametresMRP.horizon_mrp_jours`
    # (NTMFG29) — apps/mrp/tasks.py. Best-effort par société.
    'mrp-recalculer-besoins-nocturne': {
        'task': 'mrp.recalculer_besoins_nocturne',
        'schedule': crontab(hour=1, minute=30),
    },
    # NTMFG31 — archive (soft-delete) les OF prototype clôturés dépassant
    # `ParametresMRP.retention_prototype_jours` (NTMFG29) — apps/mrp/tasks.py.
    'mrp-archiver-of-prototype-anciens': {
        'task': 'mrp.archiver_of_prototype_anciens',
        'schedule': crontab(hour=2, minute=15),
    },
    # NTMFG32 — rappel proactif J-7 avant échéance d'entretien de poste
    # (NTMFG14) — apps/mrp/tasks.py.
    'mrp-rappeler-entretiens-poste-j7': {
        'task': 'mrp.rappeler_entretiens_poste_j7',
        'schedule': crontab(hour=6, minute=45),
    },
    # NTSCM35 — recalcule PolitiqueStock (NTSCM6) de chaque société avec
    # ParametresSCM configuré, tous les lundis — apps/scm/tasks.py.
    'scm-recalculer-politiques-stock-hebdo': {
        'task': 'scm.recalculer_politiques_stock_hebdo',
        'schedule': crontab(hour=5, minute=45, day_of_week=1),
    },
    # NTSCM36 — purge les PrevisionDemande > ParametresSCM.
    # retention_previsions_mois (défaut 24 mois), sauf si référencées par un
    # LigneDemandeSOP figé d'un cycle CLOS — apps/scm/tasks.py. Mensuel.
    'scm-purger-donnees-scm-anciennes': {
        'task': 'scm.purger_donnees_scm_anciennes',
        'schedule': crontab(hour=6, minute=0, day_of_month=2),
    },
    # NTSCM45 — notifie les followers/destinataires résolus d'un écart de
    # prévision (MAPE) important — apps/scm/tasks.py. Mensuel.
    'scm-notifier-ecarts-prevision-importants': {
        'task': 'scm.notifier_ecarts_prevision_importants',
        'schedule': crontab(hour=6, minute=15, day_of_month=3),
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
    # NTRET23 — libération des réservations Click & Collect expirées (annule +
    # ré-incrémente le stock si déjà sorti à la préparation). Horaire : le
    # délai d'expiration est configuré en heures côté Paramètres POS.
    'pos-liberer-reservations-expirees': {
        'task': 'pos.liberer_reservations_expirees',
        'schedule': crontab(minute=20),
    },
    # ZFSM3 — prochaine intervention de chaque récurrence active à échéance
    # (prestation périodique SANS contrat de maintenance). Idempotent.
    'installations-generer-interventions-recurrentes': {
        'task': 'installations.generer_interventions_recurrentes',
        'schedule': crontab(hour=5, minute=35),
    },
    # XPRJ13 — prochaine tâche de chaque récurrence de projet à échéance.
    'gestion-projet-generer-taches-recurrentes': {
        'task': 'gestion_projet.generer_taches_recurrentes',
        'schedule': crontab(hour=5, minute=40),
    },
    # XPRJ22 — alerte du responsable sur les projets actifs en retard/à risque
    # (jamais deux alertes pour le même (projet, élément) le même jour).
    'gestion-projet-alertes-retards-projets': {
        'task': 'gestion_projet.alertes_retards_projets',
        'schedule': crontab(hour=7, minute=18),
    },
    # XPRJ7 — rappel des ressources en retard de saisie de temps (fenêtre des
    # 7 derniers jours, même défaut que la commande).
    'gestion-projet-rappels-timesheets': {
        'task': 'gestion_projet.rappels_timesheets',
        'schedule': crontab(hour=7, minute=22),
    },
    # NTCON4 — alerte quotidienne des RFI ouverts dont la date limite de
    # réponse est dépassée (une seule alerte par jour et par RFI).
    'btp-chantier-alertes-rfi-retard': {
        'task': 'btp_chantier.alertes_rfi_retard',
        'schedule': crontab(hour=7, minute=28),
    },
    # NTCON18 — photo-rapport hebdomadaire d'avancement (lundi matin), envoyé
    # aux seuls chantiers ABONNÉS (opt-in strict) ; no-op propre sans clé email.
    'btp-chantier-rapport-photo-hebdo': {
        'task': 'btp_chantier.rapport_photo_hebdo',
        'schedule': crontab(day_of_week=1, hour=7, minute=35),
    },
    # NTPAY25 — rappel PROACTIF des échéances déclaratives de paie à J-7/J-3/
    # J-0. `notifier_echeances_en_retard` (XPAI6) ne prévenait qu'APRÈS la
    # date limite : on découvrait le retard une fois dépassé. Tôt le matin,
    # avant la journée de travail. Idempotent par échéance ET par jour-seuil
    # (marqueur de chatter `records`) — voir `apps/paie/tasks.py`.
    'paie-rappeler-echeances-declaratives': {
        'task': 'paie.rappeler_echeances_declaratives',
        'schedule': crontab(hour=6, minute=45),
    },
    # NTPAY26 — recalcul des cumuls annuels EN DÉRIVE, le 2 du mois la nuit
    # (J+1 de la clôture mensuelle : les bulletins de la veille sont figés).
    # Ne touche QUE les cumuls divergents, avec une ligne d'ajustement tracée.
    'paie-recalculer-cumuls-annuels': {
        'task': 'paie.recalculer_cumuls_annuels',
        'schedule': crontab(day_of_month=2, hour=2, minute=20),
    },
    # NTCON27 — archivage MENSUEL (1er du mois) des réserves levées depuis
    # plus de N mois (réglage par société, défaut 24). Drapeau, jamais une
    # suppression : la signature de levée reste une preuve opposable.
    'btp-chantier-archiver-reserves-levees': {
        'task': 'btp_chantier.archiver_reserves_levees',
        'schedule': crontab(day_of_month=1, hour=3, minute=40),
    },
    # NTCON28 — recalcul QUOTIDIEN du cache d'exposition aux pénalités par lot
    # (le cockpit NTCON21 lit ce cache au lieu de relancer le calcul NTCON15 à
    # chaque GET). Tôt le matin, avant les alertes RFI.
    'btp-chantier-recalculer-penalites-lots': {
        'task': 'btp_chantier.recalculer_penalites_lots',
        'schedule': crontab(hour=4, minute=10),
    },
    # NTCON37 — relance QUOTIDIENNE des visas en attente de revue dont
    # l'échéance est dépassée (revuseur + son manager). Juste après les
    # alertes RFI, même schéma qu'NTCON4.
    'btp-chantier-alertes-visas-en-attente': {
        'task': 'btp_chantier.alertes_visas_en_attente',
        'schedule': crontab(hour=7, minute=31),
    },
}


def filtrer_beat_apps_parquees(schedule, edition=None):
    """SOL2(c) — retire du beat les tâches des apps PARQUÉES par l'édition.

    Le nom d'une tâche porte l'app en préfixe (``mrp.recalculer_besoins_nocturne``,
    ``sante.alertes_prise_en_charge_expirant``…) : le filtrage se fait sur ce
    préfixe, à partir du registre STATIQUE ``erp_agentique/settings/editions.py``.

    Sans ce filtre, beat continuerait de PLANIFIER des tâches dont le module
    n'est plus chargé : chaque tick produirait un ``NotRegistered`` bruyant et
    une entrée en file que plus aucun worker ne peut consommer. En édition
    complète (défaut), rien n'est parqué → le planning est renvoyé À
    L'IDENTIQUE (aucune entrée retirée, aucun changement de comportement).
    """
    from erp_agentique.settings import editions

    parques = editions.modules_parques(edition)
    if not parques:
        return schedule
    prefixes = tuple(f'{cle}.' for cle in sorted(parques))
    return {
        nom: entree for nom, entree in schedule.items()
        if not str(entree.get('task', '')).startswith(prefixes)
    }


app.conf.beat_schedule = filtrer_beat_apps_parquees(app.conf.beat_schedule)

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
