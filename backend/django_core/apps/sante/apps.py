from django.apps import AppConfig


class SanteConfig(AppConfig):
    """NTSAN1 — Cabinet/clinique (agenda multi-praticiens, admission,
    nomenclature d'actes, facturation patient/tiers payant).

    App satellite (comme ``apps.flotte``/``apps.litiges``/``apps.qhse``) :
    multi-société, additive, scopée société côté serveur. Ce module ne stocke
    QUE des données ADMINISTRATIVES (identité, RDV, facturation) — aucune
    donnée médicale clinique (groupe NTSAN, note founder « chiffrement au
    repos pattern YHARD + (DECISION) sur chaque stockage de donnée médicale »
    — non applicable ici tant qu'aucun champ clinique n'existe).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sante'
    verbose_name = 'Santé (cabinet/clinique)'

    module_manifest = {
        'key': 'sante',
        'label': 'Santé',
        'icone': 'stethoscope',
        'depends': [],
        'description': (
            'Agenda multi-praticiens, admission, nomenclature des actes, '
            'facturation patient/tiers payant pour cabinets et cliniques.'),
        'categorie': 'Services',
    }
