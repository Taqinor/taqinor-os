from django.apps import AppConfig


class BtpChantierConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.btp_chantier'
    verbose_name = 'BTP / Chantier'
    module_manifest = {
        'key': 'btp_chantier',
        'label': 'BTP Chantier',
        'icone': 'hard-hat',
        'depends': [],
        'description': (
            'Vertical BTP/EPC : réserves géo-localisées sur plan, RFI, '
            'visas de documents techniques, journal de chantier, avenants, '
            'DGD.'
        ),
        'categorie': 'Verticaux',
    }

    def ready(self):
        # NTCON5 — abonne btp_chantier à la création d'une nouvelle version
        # GED (``ged.DocumentVersion``) pour ré-ouvrir automatiquement tout
        # visa portant sur ce document. Connexion PARESSEUSE via le registre
        # d'apps (``apps.get_model``) — aucun import statique de
        # ``ged.models`` (frontière cross-app, CLAUDE.md).
        from . import receivers  # noqa: F401
