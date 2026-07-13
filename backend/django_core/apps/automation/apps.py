from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automation'
    label = 'automation'
    verbose_name = 'Automatisations'
    module_manifest = {
        'key': 'automation',
        'label': 'Automatisations',
        'icone': 'zap',
        'depends': [],
        'description': 'Règles et approbations sans code.',
        'categorie': 'Technique',
    }

    def ready(self):
        from . import signals
        signals.connect()
        # YOPSB11 — archivage par lots du journal AutomationRun (registre
        # partagé YOPSB10). Fenêtre founder-configurable via
        # AUTOMATION_RUN_ARCHIVE_DAYS (défaut 0 = OFF, comportement inchangé).
        from core.retention import register_retention_policy, setting_days
        from .services import (
            DEFAULT_AUTOMATION_RUN_ARCHIVE_DAYS, archiver_anciens,
        )
        register_retention_policy(
            'automation_run_archive',
            lambda now, apply_: archiver_anciens(
                now,
                setting_days('AUTOMATION_RUN_ARCHIVE_DAYS',
                             DEFAULT_AUTOMATION_RUN_ARCHIVE_DAYS),
                apply_,
            ),
        )
