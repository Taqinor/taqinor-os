from django.apps import AppConfig


class ReportingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reporting'
    verbose_name = 'Reporting'
    module_manifest = {
        'key': 'reporting',
        'sku': 'generic',
        'label': 'Rapports',
        'icone': 'bar-chart',
        'depends': [],
        'description': 'Tableaux de bord et rapports.',
        'categorie': 'Technique',
    }

    def ready(self):
        # VX61 — enregistre la politique de rétention des Web Vitals dans le
        # registre partagé YOPSB10 (core.retention) : la table grossit vite
        # (une ligne par métrique par navigation).
        from core.retention import register_retention_policy
        from .services import purge_web_vitals
        register_retention_policy('reporting_web_vitals', purge_web_vitals)

        # AANA77 — adaptateurs sémantiques du CA facturé (Facture.total_ht /
        # total_ttc, D-AANA-6) : ca_ht, ca_ttc, panier_moyen.
        from .metriques_ca import register_metric_adapters
        register_metric_adapters()
