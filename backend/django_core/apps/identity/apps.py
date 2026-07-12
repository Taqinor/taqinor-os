from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """App de FONDATION identité (SSO/SCIM/politiques réseau & session).

    N'importe AUCUNE app métier ; toute donnée est scopée société côté
    serveur. Créée par la vague NTSEC (fédération d'identité & durcissement) :
    le premier modèle concret livré ici est ``NetworkPolicy`` (NTSEC11 —
    allowlist IP/CIDR par société), les modèles SSO/SCIM (NTSEC1-6) s'y
    ajouteront sans conflit.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.identity'
    label = 'identity'
    verbose_name = 'Identité & accès'
    module_manifest = {
        'key': 'identity',
        'label': 'Identité & accès',
        'icone': 'shield',
        'depends': [],
        'installable': False,
        'description': 'SSO, SCIM, politiques réseau et durcissement.',
        'categorie': 'Technique',
    }
