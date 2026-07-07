"""XSAV4 — Notifications client aux transitions du ticket SAV.

Réutilise les modèles WhatsApp/Email existants (``parametres.MessageTemplate``
/ ``parametres.EmailTemplate``, clés ``ticket_recu``/``ticket_planifie``/
``ticket_resolu``) plutôt que d'inventer un canal parallèle. Best-effort et
JAMAIS d'exception remontée à l'appelant (une notification client ratée ne
doit jamais casser une transition de ticket).

Toggle société : ``SavSlaSettings.notifications_client_sav`` (défaut False —
comportement actuel inchangé). Aucun prix interne (``cout``) n'entre jamais
dans le corps du message — seuls les placeholders whitelistés
(``{civilite}`` ``{nom}`` ``{reference}`` ``{lien}``) sont substitués.
"""
import logging

logger = logging.getLogger(__name__)

# Statut de transition → clé de template (parité WhatsApp/Email).
STATUT_TO_CLE = {
    'nouveau': 'ticket_recu',
    'planifie': 'ticket_planifie',
    'resolu': 'ticket_resolu',
}


def _nom_complet(client):
    return f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()


def build_ticket_transition_message(ticket, cle, *, request=None):
    """Construit `(sujet_ou_none, corps)` pour la clé donnée (WhatsApp = pas de
    sujet). Le lien client (FG86) est généré/résolu ici — jamais le chatter ni
    le coût interne."""
    from .models import Ticket  # noqa: F401 - documente le type attendu
    from apps.parametres.models import MessageTemplate
    from apps.parametres.models_email import EmailTemplate
    from apps.ventes.utils.whatsapp import render_message_template

    token = ticket.ensure_share_token()
    # XSAV10/XSAV19 — pointe vers la page FRONTEND /suivi/<token> (statut +
    # CSAT), pas l'API JSON brute (même origine, même patron que lien_client()
    # dans views.py et public_booking_url() XSAL17).
    if request is not None:
        lien = request.build_absolute_uri(f'/suivi/{token}')
    else:
        lien = f'/suivi/{token}'

    ctx = {
        'civilite': '', 'nom': _nom_complet(ticket.client),
        'reference': ticket.reference, 'lien': lien,
    }
    wa_corps = render_message_template(
        MessageTemplate.get_corps(ticket.company, cle), ctx)
    email = EmailTemplate.render(ticket.company, cle, **ctx)
    return wa_corps, email


def notify_ticket_transition(ticket, statut, *, request=None):
    """XSAV4 — Notifie le client d'une transition de ticket (best-effort).

    N'envoie RIEN si le toggle société est désactivé (défaut) ou si le statut
    n'a pas de clé de template associée. Ne lève jamais d'exception — une
    notification échouée est journalisée et ignorée.

    Renvoie un dict ``{'sent': bool, 'wa_draft_url': str|None,
    'email_sent': bool}`` — utile aux tests / à l'appelant, sans effet de bord
    sur le ticket lui-même.
    """
    from .models import SavSlaSettings

    result = {'sent': False, 'wa_draft_url': None, 'email_sent': False}
    cle = STATUT_TO_CLE.get(statut)
    if cle is None:
        return result

    try:
        sla = SavSlaSettings.get(ticket.company)
        if not sla.notifications_client_sav:
            return result

        wa_corps, email = build_ticket_transition_message(
            ticket, cle, request=request)

        client = ticket.client
        phone = getattr(client, 'telephone', None) if client else None
        if phone:
            from apps.ventes.services import _build_wa_draft_url
            result['wa_draft_url'] = _build_wa_draft_url(phone, wa_corps)

        email_addr = getattr(client, 'email', None) if client else None
        if email_addr:
            try:
                from django.conf import settings
                from django.core.mail import send_mail
                # Sans clé fournisseur configurée, EMAIL_BACKEND reste le
                # backend console (NO-OP réseau) — comportement identique au
                # reste de l'ERP (N87). fail_silently évite qu'un envoi raté
                # ne casse la transition de ticket.
                send_mail(
                    email['sujet'], email['corps'],
                    getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    [email_addr], fail_silently=True)
                result['email_sent'] = True
            except Exception:  # noqa: BLE001 — best-effort, jamais fatal
                logger.warning(
                    'XSAV4: envoi email transition ticket %s échoué',
                    ticket.pk, exc_info=True)

        result['sent'] = bool(result['wa_draft_url'] or result['email_sent'])
        return result
    except Exception:  # noqa: BLE001 — best-effort, jamais fatal
        logger.warning(
            'XSAV4: notification transition ticket %s échouée',
            getattr(ticket, 'pk', '?'), exc_info=True)
        return result
