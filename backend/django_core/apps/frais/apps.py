from django.apps import AppConfig


class FraisConfig(AppConfig):
    """ODX15 — Notes de frais & indemnités (équivalent Odoo « Expenses »).

    Sortie de ``apps.compta`` en STATE-ONLY (``SeparateDatabaseAndState``,
    ``db_table`` figé en ``compta_*``, zéro SQL, zéro mouvement de données).
    Le POSTING COMPTABLE reste dans ``apps.compta`` : ``apps.frais`` appelle
    ``apps.compta.services`` (écritures 6143/4432/trésorerie, verrou de période
    FG115) — jamais ses modèles.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.frais'
    verbose_name = 'Notes de frais'
    module_manifest = {
        'key': 'frais',
        'label': 'Notes de frais',
        'icone': 'receipt',
        'depends': ['rh', 'compta'],
        'description': (
            "Notes de frais, rapports de frais, plafonds de politique, "
            "barèmes et indemnités kilométriques / per-diem chantier. "
            "La validation et le remboursement postent leurs écritures via "
            "apps.compta.services."
        ),
        'categorie': 'Finance',
    }
