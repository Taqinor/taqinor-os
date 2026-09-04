import os

from django.apps import AppConfig
from django.core.checks import Warning as DjangoWarning, register


@register()
def _qjr414_whatsapp_bsp_app_secret_check(app_configs, **kwargs):
    """QJR414 (DR3) — avertit BRUYAMMENT tant que ``WHATSAPP_BSP_APP_SECRET``
    manque : le webhook BSP WhatsApp est alors FAIL-CLOSED et refuse tout POST.

    Jumeau EXACT de ``apps.crm.apps._qjr414_meta_lead_ads_app_secret_check``.
    Le secret est lu par ``views_whatsapp_bsp._app_secret`` via
    ``os.getenv`` — on le lit ici de la MÊME façon, jamais par un second
    chemin. Avertissement, jamais une erreur bloquante.
    """
    if os.getenv('WHATSAPP_BSP_APP_SECRET', '').strip():
        return []
    return [DjangoWarning(
        'WHATSAPP_BSP_APP_SECRET n\'est pas configuré : le webhook BSP '
        'WhatsApp est FAIL-CLOSED (DR3) et refuse tout POST (403). La '
        'réception des statuts de livraison reste EN PAUSE.',
        hint='Poser WHATSAPP_BSP_APP_SECRET dans le .env du serveur au '
             'prochain deploy (voir .env.example).',
        id='notifications.W010')]


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'
    module_manifest = {
        'key': 'notifications',
        'sku': 'generic',
        'label': 'Notifications',
        'icone': 'bell',
        'depends': [],
        'description': 'Moteur de notifications unifié.',
        'categorie': 'Technique',
    }

    def ready(self):
        # ERR50 — câble les producteurs (LEAD_ASSIGNED / DEVIS_ACCEPTED) pour que
        # le moteur ne soit plus inerte sur les évènements métier.
        from . import signals
        signals.connect()
