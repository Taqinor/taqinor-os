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
    """WIR216 — lien vers la section « Mes livraisons » du portail client
    (`/portail/client/livraisons`, FG228). `/portail/livraisons/<id>` n'a
    jamais existé côté front (404 systématique) : le portail est déjà
    authentifié côté client, la LISTE (scopée serveur à CE client) est la
    cible réelle — jamais un id de livraison fabriqué dans l'URL."""
    path = '/portail/client/livraisons'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def notify_livraison_transition(livraison, statut, *, request=None, user=None):
    """XSTK22 — notifie le client d'une transition de livraison (best-effort).

    N'envoie RIEN si le statut n'a pas de clé de template associée, ou si le
    client n'a ni téléphone ni email. Jamais d'exception remontée — une
    notification échouée est journalisée et ignorée. Renvoie
    ``{'sent', 'wa_draft_url', 'email_sent', 'tache_whatsapp'}`` — AMSG56 :
    ``sent`` vrai seulement si l'e-mail est réellement parti ou si le
    brouillon WhatsApp a été remis comme tâche."""
    result = {'sent': False, 'wa_draft_url': None, 'email_sent': False,
              'tache_whatsapp': False}
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
        from apps.parametres.i18n_resolver import resolve_langue_sortie
        langue = resolve_langue_sortie(client=client, company=livraison.company)  # ASOC83
        wa_corps = render_message_template(
            MessageTemplate.get_corps(livraison.company, cle, langue), ctx)
        email = EmailTemplate.render(livraison.company, cle, langue, **ctx)

        phone = getattr(client, 'telephone', None)
        if phone:
            wa_url = build_wa_url(phone, wa_corps)
            if wa_url:
                result['wa_draft_url'] = wa_url

        email_addr = getattr(client, 'email', None)
        from apps.notifications.services import _is_email_configured
        if email_addr and _is_email_configured():  # AMSG56 — envoi réel seul
            try:
                from django.conf import settings
                from django.core.mail import send_mail
                result['email_sent'] = bool(send_mail(
                    email['sujet'], email['corps'],
                    getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    [email_addr], fail_silently=False))
            except Exception:  # best-effort, jamais fatal
                logger.warning(
                    'XSTK22: envoi email transition livraison %s échoué',
                    livraison.pk, exc_info=True)
        if not result['email_sent'] and result['wa_draft_url']:
            # AMSG56 — e-mail non parti : le brouillon devient une tâche
            # « Envoyer ce WhatsApp » sur la livraison (patron APAR25).
            from apps.automation.actions import RESUME_TACHE_WHATSAPP, _creer_tache
            _creer_tache(livraison, livraison.company, user, RESUME_TACHE_WHATSAPP,
                         f"{wa_corps}\n\n{result['wa_draft_url']}")
            result['tache_whatsapp'] = True

        result['sent'] = bool(result['email_sent'] or result['tache_whatsapp'])
        return result
    except Exception:  # best-effort, jamais fatal
        logger.warning(
            'XSTK22: notification transition livraison %s échouée',
            getattr(livraison, 'pk', '?'), exc_info=True)
        return result
