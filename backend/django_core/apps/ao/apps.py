from django.apps import AppConfig


class AoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ao'
    verbose_name = "Appels d'offres (marchés publics/privés)"
    module_manifest = {
        'key': 'ao',
        'label': "Appels d'offres",
        'icone': 'gavel',
        'depends': ['crm', 'ventes'],
        'description': (
            "Gestion des appels d'offres publics/privés : bordereaux de prix "
            "(BOQ), cautions/garanties de soumission, dossier administratif, "
            "échéancier de deadlines et analyse gagné/perdu."
        ),
        'categorie': 'Commercial',
    }

    def ready(self):
        # AOF29 — péremption automatique EN CASCADE des variantes de
        # calepinage : toute écriture d'obstacle, de cote ou d'enveloppe
        # recalcule l'empreinte d'entrée et bascule ``PERIME`` ce qui diverge.
        # Borné à LA toiture touchée (péremption GRANULAIRE).
        from . import receivers  # noqa: F401
        # AOF168 — fournisseur DSR (loi 09-08) du domaine AO : export et
        # ANONYMISATION (jamais suppression) des identités portées par les
        # relevés et les séries de questions. Patron `apps/crm/apps.py`.
        from . import dsr
        dsr.register()
        # AOF168 — politiques de rétention des ARTEFACTS d'AO (photos de
        # relevé, images annotées de questions, plans sources) sur le registre
        # partagé YOPSB10. Chaque fenêtre vaut 0 = OFF par défaut : rien n'est
        # purgé tant que le fondateur n'a pas posé son réglage, et seuls les
        # AO perdus/abandonnés sont éligibles.
        from . import retention
        retention.register()
