from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'
    label = 'audit'
    verbose_name = "Journal d'activité"
    module_manifest = {
        'key': 'audit',
        'sku': 'generic',
        'label': "Journal d'activité",
        'icone': 'history',
        'depends': [],
        'installable': False,
        'description': "Journal d'audit des actions.",
        'categorie': 'Technique',
    }

    def ready(self):
        from . import signals
        signals.connect()
        # M4 — abonne le satellite audit aux événements métier (core.events) :
        # journalise un PDF (AuditLog.Action.PDF) sur document_pdf_generated,
        # sans que ventes importe apps.audit (suppression de l'arête montante
        # ventes → audit). Voir la « carte des trois couches » dans core/events.
        from . import receivers  # noqa: F401
        # ENF20 — branche le recorder comme enregistreur générique de `core`
        # (`core.audit_registry`, même pattern que `core.notify_registry`) :
        # stock/automation/dataimport journalisent SANS importer apps.audit.
        from core.audit_registry import enregistrer
        from .recorder import current_user, record
        enregistrer(record, current_user=current_user)
