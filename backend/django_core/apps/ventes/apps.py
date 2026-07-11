import os

from django.apps import AppConfig
from django.core.checks import Warning as DjangoWarning, register


@register()
def _qx10_esign_otp_channel_check(app_configs, **kwargs):
    """QX10 — avertit si ``ESIGN_OTP_ENABLED`` est actif alors que le seul
    canal OTP disponible est le STUB WhatsApp (aucun BSP câblé).

    Sans email configuré, un client téléphone-seul ne peut alors PAS recevoir
    son code → il est bloqué hors de la signature. Simple avertissement au
    démarrage (jamais une erreur bloquante)."""
    warnings = []
    if os.getenv('ESIGN_OTP_ENABLED', '0').strip() == '1':
        try:
            from apps.ventes.email_service import is_email_configured
            email_ok = is_email_configured()
        except Exception:  # noqa: BLE001
            email_ok = False
        if not email_ok:
            warnings.append(DjangoWarning(
                'ESIGN_OTP_ENABLED est actif mais le seul canal OTP est le '
                'stub WhatsApp (aucun BSP câblé) et aucun email n\'est '
                'configuré : les clients téléphone-seul ne recevront pas leur '
                'code et ne pourront pas signer.',
                hint='Configurer un backend email (BREVO_API_KEY/SENDGRID) ou '
                     'câbler un BSP WhatsApp avant d\'activer ESIGN_OTP_ENABLED.',
                id='ventes.W010'))
    return warnings


class VentesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ventes'
    verbose_name = 'Ventes'
    module_manifest = {
        'key': 'ventes',
        'label': 'Ventes',
        'icone': 'file-text',
        'depends': ['crm'],
        'description': 'Devis, bons de commande et facturation.',
        'categorie': 'Ventes',
    }

    def ready(self):
        # AG4/AG5 — enregistre les actions agentiques Ventes (flux devis →
        # facture → encaissement) dans le registre AG1. Import local pour
        # éviter les effets de bord à l'import et d'éventuels cycles au
        # démarrage. Idempotent si ready() est appelé plusieurs fois.
        from .agent_actions import register_ventes_actions
        register_ventes_actions()
        # YLEDG12 — abonne ventes à `payment_captured` (core FG370) : câble
        # les récepteurs du bus d'événements (M6). Import local, jamais
        # d'effet de bord à l'import du module.
        from . import receivers  # noqa: F401
        # QX24 — connecte les signaux LigneDevis (post_save/post_delete) qui
        # gardent le payback de l'étude cohérent avec le total courant.
        receivers._register_qx24_signals()
        # QX36 — abonne le handler email entrant (réponse client → chatter +
        # notification sur le devis) au bus core.email_intake.
        from .inbound_email import register_ventes_inbound_handler
        register_ventes_inbound_handler()
