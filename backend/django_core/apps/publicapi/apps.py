from django.apps import AppConfig


class PublicApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.publicapi'
    label = 'publicapi'
    verbose_name = 'API publique'
    module_manifest = {
        'key': 'publicapi',
        'sku': 'generic',
        'label': 'API publique',
        'icone': 'globe',
        'depends': [],
        'installable': False,
        'description': 'Clés API et webhooks (géré par clés API).',
        'categorie': 'Technique',
    }

    def ready(self):
        # Branche les signaux qui déclenchent les webhooks sur les évènements
        # métier (nouveau lead, devis accepté, chantier clôturé, facture payée).
        from . import signals
        signals.connect()
        # NTSCM39 — abonnés aux évènements SCM du bus `core.events`
        # (`scm_rupture_imminente_detectee`/`scm_cycle_sop_cloture`), jamais
        # un import direct `apps.scm` -> `apps.publicapi`.
        from . import scm_event_receivers
        scm_event_receivers.connect()
        # YOPSB11 — archivage par lots du journal WebhookDelivery (registre
        # partagé YOPSB10). Fenêtre founder-configurable via
        # WEBHOOK_DELIVERY_ARCHIVE_DAYS (défaut 0 = OFF, comportement inchangé).
        from core.retention import register_retention_policy, setting_days
        from .services import (
            DEFAULT_WEBHOOK_DELIVERY_ARCHIVE_DAYS, archiver_anciens,
        )
        register_retention_policy(
            'publicapi_webhook_delivery_archive',
            lambda now, apply_: archiver_anciens(
                now,
                setting_days('WEBHOOK_DELIVERY_ARCHIVE_DAYS',
                             DEFAULT_WEBHOOK_DELIVERY_ARCHIVE_DAYS),
                apply_,
            ),
        )
        # NTAPI17 — rétention du flux d'évènements, bornée PAR SOCIÉTÉ par son
        # plan (`ApiUsagePlan.retention_livraisons_jours`, NTAPI7) : le flux est
        # le même matériau qu'une livraison webhook et suit donc la même borne,
        # jamais une seconde notion de rétention à régler ailleurs. Société sans
        # plan → `API_EVENT_RETENTION_DAYS` (défaut 0 = OFF, rien n'est purgé).
        from .events_feed import purger_evenements
        register_retention_policy(
            'publicapi_api_event_retention',
            lambda now, apply_: purger_evenements(now, apply_),
        )
