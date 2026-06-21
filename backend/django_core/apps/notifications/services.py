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

from .models import (
    Channel, EventType, Notification, NotificationPreference,
    NotificationRoutingRule,
)

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

# ERR91 — Bornes cohérentes pour la ligne in-app. `title` (255) et `link` (512)
# sont déjà tronqués sur leur taille de colonne ; le corps (TextField, sans
# limite de colonne) l'était pas — un appelant pouvait écrire une notification
# arbitrairement grosse. On borne le corps de façon cohérente.
MAX_BODY_LEN = 2000


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


def resolve_vapid_keys():
    """Renvoie la paire VAPID effective `(public, private)`.

    Précédence (N109) :
      1. clés d'environnement (`settings.VAPID_PUBLIC_KEY/PRIVATE_KEY`) si TOUTES
         DEUX non vides → on les utilise telles quelles ;
      2. sinon, si l'auto-génération est désactivée (`VAPID_AUTOGENERATE` faux),
         on renvoie les valeurs d'env (possiblement vides) SANS toucher la base —
         ce qui préserve le contrat « clés vides => endpoint vide => no-op » des
         tests ;
      3. sinon, on assure le singleton `VapidKeyPair` (génère+persiste si besoin)
         et on renvoie sa paire ; en cas d'échec on retombe sur les valeurs d'env.

    Best-effort : jamais d'exception remontée."""
    try:
        from django.conf import settings
        env_pub = getattr(settings, 'VAPID_PUBLIC_KEY', '') or ''
        env_priv = getattr(settings, 'VAPID_PRIVATE_KEY', '') or ''
        if env_pub and env_priv:
            return (env_pub, env_priv)
        if not getattr(settings, 'VAPID_AUTOGENERATE', False):
            return (env_pub, env_priv)
        from .models import VapidKeyPair
        kp = VapidKeyPair.ensure()
        if kp is not None and kp.public_key and kp.private_key:
            return (kp.public_key, kp.private_key)
        return (env_pub, env_priv)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('Résolution des clés VAPID échouée : %s', exc)
        return ('', '')


def _is_webpush_configured():
    """True si une paire VAPID est réellement disponible (les deux clés résolues).

    Sans clé privée, le push est un NO-OP total — aucune dépendance d'envoi n'est
    même chargée. C'est l'interrupteur qui préserve le comportement actuel."""
    try:
        public, private = resolve_vapid_keys()
        return bool(public and private)
    except Exception:  # pragma: no cover - défensif
        return False


def _dispatch_webpush(user, title, body, link=None):
    """Best-effort : envoie un Web Push à TOUS les appareils de l'utilisateur.

    NO-OP silencieux si les clés VAPID sont absentes OU si l'utilisateur n'a
    aucun abonnement. Erreurs avalées+journalisées ; un abonnement expiré
    (HTTP 404/410) est SUPPRIMÉ. Renvoie le nombre d'envois réussis."""
    if not _is_webpush_configured():
        return 0
    try:
        from .models import PushSubscription
        subs = list(PushSubscription.objects.filter(user=user))
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('Chargement des abonnements push échoué : %s', exc)
        return 0
    if not subs:
        return 0

    try:
        import json

        from django.conf import settings
        from pywebpush import WebPushException, webpush
    except Exception as exc:  # pragma: no cover - lib absente / non installée
        logger.warning('pywebpush indisponible, push ignoré : %s', exc)
        return 0

    payload = json.dumps({
        'title': str(title), 'body': str(body or ''),
        'link': str(link or ''),
    })
    # Sujet VAPID (contact du serveur applicatif). Apple Web Push REJETTE un
    # sujet non routable — ex. l'ancien défaut `mailto:admin@erp.local` — avec
    # `403 BadJwtToken` et abandonne SILENCIEUSEMENT chaque push iOS (FCM/Chrome
    # est laxiste, d'où « ça marche sur Windows mais pas sur iPhone »). À défaut
    # d'email configuré (`VAPID_ADMIN_EMAIL`), on retombe donc sur l'URL https: de
    # production — un sujet VAPID valide (RFC 8292) accepté par Apple — pour que le
    # push iPhone fonctionne sans configuration serveur supplémentaire.
    admin_email = (getattr(settings, 'VAPID_ADMIN_EMAIL', '') or '').strip()
    sub = f'mailto:{admin_email}' if admin_email else 'https://taqinor.ma'
    claims = {'sub': sub}
    # Clé privée résolue (env si fournie, sinon singleton auto-généré).
    _public, private_key = resolve_vapid_keys()

    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub.as_subscription_info(),
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=dict(claims),
            )
            sent += 1
        except WebPushException as exc:  # pragma: no cover - dépend du réseau
            # Abonnement périmé / désinscrit côté navigateur → on le retire.
            resp = getattr(exc, 'response', None)
            code = getattr(resp, 'status_code', None)
            if code in (404, 410):
                try:
                    sub.delete()
                except Exception:  # pragma: no cover - défensif
                    pass
            else:
                logger.warning('Web push échoué (sub %s) : %s', sub.pk, exc)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Web push échoué (sub %s) : %s', sub.pk, exc)
    return sent


def resolve_recipients(company, event_type):
    """FG4 — Résout la liste des destinataires pour un événement et une société.

    Si des `NotificationRoutingRule` actives existent pour cet événement et
    cette société, on les consulte pour construire la liste des destinataires :
      - règle avec `target_user` → cet utilisateur directement ;
      - règle avec `target_role` → tous les utilisateurs actifs de la société
        ayant ce `role_legacy`.

    Si AUCUNE règle n'est configurée pour cet événement + société, on retombe
    sur le comportement historique : les managers (role_legacy in admin/responsable)
    actifs de la société.

    Retourne un QuerySet d'utilisateurs (peut être vide). Best-effort :
    toute erreur renvoie un QuerySet vide plutôt que de propager l'exception."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        rules = list(NotificationRoutingRule.objects.filter(
            company=company, event_type=event_type, enabled=True
        ).select_related('target_user'))

        if not rules:
            # Comportement historique : managers actifs de la société.
            return User.objects.filter(
                company=company, is_active=True,
                role_legacy__in=['admin', 'responsable'])

        # Construire l'ensemble des PKs destinataires depuis les règles actives.
        user_pks = set()
        role_targets = []
        for rule in rules:
            if rule.target_user_id:
                user_pks.add(rule.target_user_id)
            elif rule.target_role:
                role_targets.append(rule.target_role)

        from django.db.models import Q
        q = Q(pk__in=user_pks)
        if role_targets:
            q |= Q(company=company, is_active=True, role_legacy__in=role_targets)
        return User.objects.filter(q, company=company, is_active=True)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('resolve_recipients échoué : %s', exc)
        from django.contrib.auth import get_user_model
        return get_user_model().objects.none()


def notify_many(recipients, event_type, title, body='', link=None, company=None):
    """Émet une notification vers une liste de destinataires.

    Appelle `notify()` pour chaque utilisateur. Best-effort par destinataire :
    une erreur sur l'un n'interrompt pas les suivants."""
    created = []
    for user in recipients:
        try:
            n = notify(user, event_type, title, body=body, link=link, company=company)
            if n is not None:
                created.append(n)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('notify_many: notification échouée vers %s : %s', user, exc)
    return created


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
                title=str(title)[:255], body=str(body or '')[:MAX_BODY_LEN],
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

    # Web push (N92) : best-effort, opt-in par APPAREIL (pas un toggle
    # d'événement). NO-OP total sans clés VAPID ni abonnement — donc aucun
    # changement de comportement tant que rien n'est configuré.
    try:
        _dispatch_webpush(user, str(title), str(body or ''), link=link)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('Dispatch web push notification échoué : %s', exc)

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
