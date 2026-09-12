from django.apps import AppConfig


class GrcConfig(AppConfig):
    """Groupe NTGRC — GRC & Privacy (gouvernance, risques, conformité).

    App satellite multi-société. Elle ÉTEND le socle RGPD/loi 09-08 déjà posé
    en fondation (``core.RegistreTraitement`` / ``core.ConsentRecord`` /
    ``core.DataSubjectRequest`` + les registres ``core.dsr`` et
    ``core.retention``) — elle ne le duplique JAMAIS. Elle lit les autres apps
    uniquement via leurs ``selectors.py``/``services.py`` ou par FK déclarée en
    CHAÎNE ; aucun import de leurs ``models``.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.grc'
    label = 'grc'
    verbose_name = 'GRC & Conformité'
    module_manifest = {
        'key': 'grc',
        'sku': 'generic',
        'label': 'GRC & Conformité',
        'icone': 'shield-check',
        'depends': [],
        'installable': True,
        'description': ('Gouvernance, risques et conformité : registre des '
                        'risques, contrôles internes, RGPD/loi 09-08 outillé, '
                        'rétention et journal de destruction.'),
        'categorie': 'Technique',
    }
