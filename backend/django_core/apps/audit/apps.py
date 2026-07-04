from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'
    label = 'audit'
    verbose_name = "Journal d'activité"
    module_manifest = {
        'key': 'audit',
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
