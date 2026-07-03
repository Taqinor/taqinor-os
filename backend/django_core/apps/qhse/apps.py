from django.apps import AppConfig


class QhseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.qhse'
    verbose_name = 'QHSE'

    def ready(self):
        # QHSE32 — abonne QHSE à l'événement incident_declared (bus de signaux
        # Django) pour escalader les incidents critiques, sur le patron de
        # ventes→crm. Même app émettrice et abonnée : le signal vit dans qhse.
        # XQHS3 — le même module abonne aussi qhse à l'événement INTER-app
        # core.events.reception_fournisseur_confirmee (émetteur = stock) pour
        # ouvrir les contrôles qualité de réception.
        from . import receivers  # noqa: F401
