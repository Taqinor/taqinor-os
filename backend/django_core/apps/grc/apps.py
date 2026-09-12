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

    def ready(self):
        # NTGRC8 — garde d'effacement : un dossier sous séquestre (legal hold)
        # ne s'anonymise pas, même sur demande légale, tant que le séquestre
        # est actif. `core.dsr` la consulte AVANT tout effacement ; `core` ne
        # connaît que le nom et le callable (il reste fondation).
        from .services import register_erasure_guard
        register_erasure_guard()
        # NTGRC9 — abonnements au bus `core.events` (M6) : alerte DPO quand une
        # personne ayant RETIRÉ son consentement est de nouveau traitée
        # (nouveau lead, devis accepté). `grc` n'importe ni crm ni ventes.
        from . import receivers  # noqa: F401
