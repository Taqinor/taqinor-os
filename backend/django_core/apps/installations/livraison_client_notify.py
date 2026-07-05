"""XSTK22 — notification client au passage en transit/livrée d'une livraison.

Réutilise les modèles WhatsApp/Email existants (``parametres.MessageTemplate``
/ ``parametres.EmailTemplate``, clés ``livraison_en_transit``/
``livraison_livree`` — même patron que ``apps.sav.notifications_client``
XSAV4). Best-effort et JAMAIS d'exception remontée à l'appelant : une
notification client ratée ne doit jamais casser une transition de livraison.

Le lien pointe vers la section « Livraisons » du portail (FG228) — jamais un
identifiant interne (``cout_transport``, prix d'achat)."""
import logging

logger = logging.getLogger(__name__)

STATUT_TO_CLE = {
    'en_transit': 'livraison_en_transit',
    'livree': 'livraison_livree',
}


def _nom_complet(client):
    if client is None:
        return ''
    return f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()


def _livraison_lien(livraison, request=None):
    """Lien indicatif vers la section Livraisons du portail (pas de token
    dédié ici — le portail est déjà authentifié côté client, FG228)."""
    path = f'/portail/livraisons/{livraison.id}'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def notify_livraison_transition(livraison, statut, *, request=None):
    """XSTK22 — notifie le client d'une transition de livraison (best-effort).

    N'envoie RIEN si le statut n'a pas de clé de template associée, ou si le
    client n'a ni téléphone ni email. Jamais d'exception remontée — une
    notification échouée est journalisée et ignorée. Renvoie
    ``{'sent': bool, 'wa_draft_url': str|None, 'email_sent': bool}``."""
    result = {'sent': False, 'wa_draft_url': None, 'email_sent': False}
    cle = STATUT_TO_CLE.get(statut)
    if cle is None:
        return result

    try:
        from apps.parametres.models import MessageTemplate
        from apps.parametres.models_email import EmailTemplate
        from apps.ventes.utils.whatsapp import (
            render_message_template, build_wa_url,
        )

        installation = livraison.installation
        client = getattr(installation, 'client', None) if installation else None
        if client is None:
            return result

        ctx = {
            'civilite': '', 'nom': _nom_complet(client),
            'reference': livraison.reference,
            'lien': _livraison_lien(livraison, request=request),
        }
        wa_corps = render_message_template(
            MessageTemplate.get_corps(livraison.company, cle), ctx)
        email = EmailTemplate.render(livraison.company, cle, **ctx)

        phone = getattr(client, 'telephone', None)
        if phone:
            wa_url = build_wa_url(phone, wa_corps)
            if wa_url:
                result['wa_draft_url'] = wa_url

        email_addr = getattr(client, 'email', None)
        if email_addr:
            try:
                from django.conf import settings
                from django.core.mail import send_mail
                # Sans clé fournisseur configurée, EMAIL_BACKEND reste le
                # backend console (NO-OP réseau) — comportement identique au
                # reste de l'ERP (N87). fail_silently évite qu'un envoi raté
                # ne casse la transition de livraison.
                send_mail(
                    email['sujet'], email['corps'],
                    getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    [email_addr], fail_silently=True)
                result['email_sent'] = True
            except Exception:  # noqa: BLE001 — best-effort, jamais fatal
                logger.warning(
                    'XSTK22: envoi email transition livraison %s échoué',
                    livraison.pk, exc_info=True)

        result['sent'] = bool(result['wa_draft_url'] or result['email_sent'])
        return result
    except Exception:  # noqa: BLE001 — best-effort, jamais fatal
        logger.warning(
            'XSTK22: notification transition livraison %s échouée',
            getattr(livraison, 'pk', '?'), exc_info=True)
        return result
