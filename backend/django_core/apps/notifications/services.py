"""N75 — Service d'émission de notifications.

`notify(user, event_type, title, body, link=None)` est le SEUL point d'entrée.
Il respecte les préférences de l'utilisateur :
  - crée TOUJOURS la ligne in-app quand le canal in-app est activé pour cet
    événement (défaut : activé) ;
  - diffuse vers WhatsApp / email / SMS via les intégrations EXISTANTES
    uniquement si le canal est activé ET réellement configuré.

La diffusion hors-app est best-effort : toute erreur est capturée et journalisée,
JAMAIS propagée à l'appelant — émettre une notification ne doit jamais casser le
flux métier qui la déclenche. Sans configuration, les canaux hors-app sont des
NO-OP silencieux (comportement actuel préservé).
"""
import logging

from django.utils import timezone

from .models import Channel, EventType, Notification, NotificationPreference

logger = logging.getLogger(__name__)


# Défauts sensibles, par événement. In-app activé partout ; les canaux hors-app
# restent désactivés par défaut (rien de spammeur). L'utilisateur peut les
# activer dans ses préférences. Ces défauts s'appliquent en l'ABSENCE de ligne
# NotificationPreference.
DEFAULT_PREFS = {
    'in_app': True,
    'whatsapp': False,
    'email': False,
}


def default_prefs_for(event_type):
    """Retourne les toggles par défaut pour un événement (copie mutable)."""
    return dict(DEFAULT_PREFS)


def resolve_prefs(user, event_type):
    """Préférences effectives (ligne stockée sinon défauts). Best-effort."""
    try:
        pref = NotificationPreference.objects.filter(
            user=user, event_type=event_type).first()
    except Exception:  # pragma: no cover - défensif
        pref = None
    if pref is None:
        return default_prefs_for(event_type)
    return {
        'in_app': pref.in_app,
        'whatsapp': pref.whatsapp,
        'email': pref.email,
    }


def _is_email_configured():
    """Réutilise l'helper de configuration email des ventes (Brevo/SMTP)."""
    try:
        from apps.ventes.email_service import is_email_configured
        return is_email_configured()
    except Exception:  # pragma: no cover - défensif
        return False


def _dispatch_email(user, title, body):
    """Diffuse une notification par email via le backend Django configuré.

    NO-OP silencieux si l'email n'est pas configuré ou si l'utilisateur n'a pas
    d'adresse. Best-effort : jamais d'exception remontée."""
    dest = (getattr(user, 'email', '') or '').strip()
    if not dest or not _is_email_configured():
        return False
    try:
        from django.conf import settings
        from django.core.mail import EmailMessage, get_connection
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'noreply@erp.local'
        connection = get_connection(fail_silently=True)
        EmailMessage(
            subject=title[:300], body=body or title,
            from_email=from_email, to=[dest], connection=connection,
        ).send(fail_silently=True)
        return True
    except Exception as exc:  # pragma: no cover - dépend du backend réel
        logger.warning('Notification email échouée vers %s : %s', dest, exc)
        return False


def _whatsapp_link(user, title, body):
    """Construit un lien wa.me PRÊT à envoyer (pas d'envoi automatique).

    Réutilise le builder d'URL WhatsApp existant. Renvoie l'URL ou None. La
    plateforme WhatsApp ne permet pas d'envoi serveur sans l'API payante : on se
    contente de préparer le lien (no-op fonctionnel), comme le reste de l'ERP."""
    phone = (getattr(user, 'phone_number', '') or '').strip()
    if not phone:
        return None
    try:
        from apps.ventes.utils.whatsapp import build_wa_url
        message = title if not body else f'{title}\n\n{body}'
        return build_wa_url(phone, message)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('Lien WhatsApp de notification échoué : %s', exc)
        return None


def _dispatch_whatsapp(user, title, body):
    """Best-effort : prépare le lien WhatsApp (no-op si numéro absent)."""
    url = _whatsapp_link(user, title, body)
    return bool(url)


def notify(user, event_type, title, body='', link=None, company=None):
    """Émet une notification pour `user` en respectant ses préférences.

    - Crée la ligne in-app si le canal in-app est activé (défaut : oui).
    - Diffuse vers email/WhatsApp si le canal est activé ET configuré
      (best-effort, jamais d'exception remontée).

    `event_type` doit appartenir à `EventType`. La société est déduite de
    l'utilisateur (jamais du corps de requête) sauf override explicite côté
    serveur. Renvoie la `Notification` créée, ou None si in-app désactivé.
    """
    if user is None or not getattr(user, 'pk', None):
        return None
    if event_type not in EventType.values:
        logger.warning('notify(): type d\'événement inconnu %r', event_type)
        return None

    company = company if company is not None else getattr(user, 'company', None)
    prefs = resolve_prefs(user, event_type)

    created = None
    if prefs.get('in_app'):
        try:
            created = Notification.objects.create(
                company=company, recipient=user, event_type=event_type,
                title=str(title)[:255], body=str(body or ''),
                link=str(link or '')[:512])
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Création notification in-app échouée : %s', exc)
            created = None

    # Diffusions hors-app : best-effort, chacune isolée.
    if prefs.get('email'):
        try:
            _dispatch_email(user, str(title), str(body or ''))
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Dispatch email notification échoué : %s', exc)
    if prefs.get('whatsapp'):
        try:
            _dispatch_whatsapp(user, str(title), str(body or ''))
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Dispatch WhatsApp notification échoué : %s', exc)

    return created


def merged_preferences(user):
    """Liste des préférences effectives pour TOUS les événements (UI).

    Combine les défauts avec les lignes stockées de l'utilisateur. Ne crée
    aucune ligne en base."""
    stored = {}
    try:
        for p in NotificationPreference.objects.filter(user=user):
            stored[p.event_type] = p
    except Exception:  # pragma: no cover - défensif
        stored = {}
    out = []
    for value, label in EventType.choices:
        p = stored.get(value)
        if p is not None:
            out.append({
                'event_type': value, 'event_label': label,
                'in_app': p.in_app, 'whatsapp': p.whatsapp, 'email': p.email,
            })
        else:
            d = default_prefs_for(value)
            out.append({
                'event_type': value, 'event_label': label,
                'in_app': d['in_app'], 'whatsapp': d['whatsapp'],
                'email': d['email'],
            })
    return out


# Réexport pratique des libellés de canaux (UI).
CHANNELS = [
    {'key': Channel.IN_APP, 'label': 'In-app'},
    {'key': Channel.WHATSAPP, 'label': 'WhatsApp'},
    {'key': Channel.EMAIL, 'label': 'Email'},
]


def mark_read_at():
    return timezone.now()
