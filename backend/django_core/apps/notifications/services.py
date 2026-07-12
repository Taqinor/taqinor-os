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

# QW8 — Le founder a choisi « email gratuit maintenant » pour l'obligation de
# rappel (QW4) : le canal email est activé PAR DÉFAUT pour ces deux événements
# (override par événement) — un rappel demandé mérite mieux qu'une simple
# ligne in-app qui peut passer inaperçue. Reste surchargeable par une ligne
# ``NotificationPreference`` explicite (``resolve_prefs`` la préfère toujours).
EVENT_DEFAULT_OVERRIDES = {
    'lead_callback_requested': {'email': True},
    'lead_callback_sla_breach': {'email': True},
}

# ERR91 — Bornes cohérentes pour la ligne in-app. `title` (255) et `link` (512)
# sont déjà tronqués sur leur taille de colonne ; le corps (TextField, sans
# limite de colonne) l'était pas — un appelant pouvait écrire une notification
# arbitrairement grosse. On borne le corps de façon cohérente.
MAX_BODY_LEN = 2000


def default_prefs_for(event_type):
    """Retourne les toggles par défaut pour un événement (copie mutable).

    QW8 — applique un override par événement (``EVENT_DEFAULT_OVERRIDES``)
    quand il existe, sinon les défauts génériques ``DEFAULT_PREFS``."""
    prefs = dict(DEFAULT_PREFS)
    prefs.update(EVENT_DEFAULT_OVERRIDES.get(event_type, {}))
    return prefs


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


def _branded_html(company, sujet, corps):
    """VX76 — wrapper HTML de marque (logo + en-tête navy + pied) autour du
    corps texte existant. Best-effort : jamais d'exception, jamais de
    changement du corps texte brut conservé en repli MIME."""
    try:
        from apps.parametres.selectors import company_identity
        from core.selectors import wrap_email_html
        identite = company_identity(company) if company is not None else {}
        return wrap_email_html(
            sujet, corps,
            company_nom=identite.get('nom', ''),
            company_adresse=identite.get('adresse', ''),
            company_telephone=identite.get('telephone', ''),
            company_email=identite.get('email', ''),
            couleur_principale=identite.get('couleur_principale', ''),
        )
    except Exception:  # noqa: BLE001 — un email ne casse jamais sur ce point
        return ''


def _dispatch_email(user, title, body):
    """Diffuse une notification par email via le backend Django configuré.

    NO-OP silencieux si l'email n'est pas configuré ou si l'utilisateur n'a pas
    d'adresse. Best-effort : jamais d'exception remontée.

    VX76 — le corps texte reste le corps MIME principal (repli ``text/plain``
    inchangé) ; une alternative ``text/html`` brandée (wrapper logo/en-tête
    navy/pied) est ajoutée quand le rendu réussit — additif, jamais cassant."""
    dest = (getattr(user, 'email', '') or '').strip()
    if not dest or not _is_email_configured():
        return False
    try:
        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives, get_connection
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'noreply@erp.local'
        connection = get_connection(fail_silently=True)
        corps = body or title
        msg = EmailMultiAlternatives(
            subject=title[:300], body=corps,
            from_email=from_email, to=[dest], connection=connection,
        )
        html = _branded_html(getattr(user, 'company', None), title, corps)
        if html:
            msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=True)
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


def _vapid_private_for_push(private_key):
    """Convertit la clé privée VAPID stockée vers une forme acceptée par
    ``pywebpush.webpush(vapid_private_key=...)``.

    pywebpush attend un CHEMIN de fichier PEM, une chaîne base64(DER), ou un objet
    ``Vapid``. Il N'accepte PAS le TEXTE d'un PEM passé directement (il le décode
    en base64 → « Could not deserialize key data / ASN.1 invalid length »). Le
    singleton auto-généré stocke la clé en PEM : on la charge donc en objet
    ``Vapid01``. Une clé d'environnement déjà en base64url brut est renvoyée telle
    quelle. Best-effort : en cas d'échec on renvoie la valeur d'origine."""
    if not private_key or 'BEGIN' not in private_key:
        return private_key
    try:
        from py_vapid import Vapid01
        return Vapid01.from_pem(private_key.encode())
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('Chargement de la clé VAPID (PEM) échoué : %s', exc)
        return private_key


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
    # pywebpush n'accepte PAS le TEXTE d'un PEM passé en chaîne : il tente de le
    # décoder en base64 → « Could not deserialize key data / ASN.1 invalid
    # length », et CHAQUE push échoue (tous appareils). Le singleton stocke la clé
    # en PEM → on la charge ici en objet Vapid (forme acceptée). La paire ne
    # change pas : les abonnements existants restent valides.
    vapid_private = _vapid_private_for_push(private_key)

    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub.as_subscription_info(),
                data=payload,
                vapid_private_key=vapid_private,
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


def resolve_recipients_reason(company, event_type):
    """VX212(a) — la raison (`models.NotificationReason`) qu'appliquera
    `resolve_recipients` pour cet événement+société : `'regle_de_routage'`
    si une `NotificationRoutingRule` active existe, sinon `'manager'` (repli
    historique — managers actifs). Best-effort : toute erreur renvoie ''
    (raison non classée) plutôt qu'une exception."""
    try:
        from .models import NotificationReason
        exists = NotificationRoutingRule.objects.filter(
            company=company, event_type=event_type, enabled=True).exists()
        return (NotificationReason.ROUTING_RULE if exists
                else NotificationReason.MANAGER)
    except Exception:  # pragma: no cover - défensif
        return ''


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


def notify_many(recipients, event_type, title, body='', link=None, company=None,
                reason=''):
    """Émet une notification vers une liste de destinataires.

    Appelle `notify()` pour chaque utilisateur. Best-effort par destinataire :
    une erreur sur l'un n'interrompt pas les suivants. `reason` (VX212(a)) —
    transmise telle quelle à chaque `notify()`."""
    created = []
    for user in recipients:
        try:
            n = notify(user, event_type, title, body=body, link=link,
                       company=company, reason=reason)
            if n is not None:
                created.append(n)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('notify_many: notification échouée vers %s : %s', user, exc)
    return created


def _in_quiet_hours_non_critique(event_type, company, respect_quiet_hours):
    """VX209(a) — True si les canaux HORS-APP de `event_type` doivent être
    tus MAINTENANT pour `company` : le flag est actif, l'événement n'est PAS
    critique (`severity.severity_of`), et l'instant présent tombe dans la
    fenêtre de silence (nuit ou jour férié/non-ouvré,
    `selectors.est_hors_fenetre_silence`). L'in-app n'est JAMAIS concerné —
    seul l'appelant de `notify()` décide d'en tenir compte pour email/
    WhatsApp/push. Best-effort : toute erreur retombe sur `False` (ne JAMAIS
    faire échouer une notification pour une histoire d'heures calmes)."""
    if not respect_quiet_hours:
        return False
    try:
        from . import severity as severity_module
        if severity_module.severity_of(event_type) == severity_module.CRITIQUE:
            return False
        from . import selectors as notifications_selectors
        return notifications_selectors.est_hors_fenetre_silence(
            timezone.now(), company)
    except Exception:  # pragma: no cover - défensif
        return False


def notify(user, event_type, title, body='', link=None, company=None,
           skip_email=False, reason='', respect_quiet_hours=True):
    """Émet une notification pour `user` en respectant ses préférences.

    - Crée la ligne in-app si le canal in-app est activé (défaut : oui) —
      TOUJOURS immédiate, jamais différée par les heures calmes.
    - Diffuse vers email/WhatsApp/push si le canal est activé ET configuré
      (best-effort, jamais d'exception remontée).

    `event_type` doit appartenir à `EventType`. La société est déduite de
    l'utilisateur (jamais du corps de requête) sauf override explicite côté
    serveur. Renvoie la `Notification` créée, ou None si in-app désactivé.

    `skip_email` (ZCTR12) : permet à un appelant qui gère DÉJÀ sa propre
    diffusion email pour ce même événement (ex. le fan-out canal-aliasé
    e-mail du chat) d'éviter un double envoi — in-app/WhatsApp/push
    restent inchangés.

    `reason` (VX212(a)) : raison COURTE optionnelle (`models.
    NotificationReason`) — « pourquoi je reçois ça », posée par l'appelant
    QUAND il la connaît (ex. `_managers(company)` → `'manager'`). Une valeur
    hors énumération est silencieusement ignorée (jamais une exception) ;
    vide = raison non classée, comportement historique inchangé.

    `respect_quiet_hours` (VX209(a), défaut `True`) : quand l'événement n'est
    PAS classé `'critique'` (`severity.EVENT_SEVERITY`) et que l'instant
    présent tombe dans la fenêtre de silence de `company` (nuit stricte ou
    jour férié/non-ouvré — `selectors.est_hors_fenetre_silence`), les canaux
    HORS-APP (email/WhatsApp/push) sont SKIPPÉS pour cet appel — la ligne
    in-app reste créée normalement. Un événement `'critique'` part toujours,
    à toute heure. Passer `False` préserve le comportement historique (envoi
    à toute heure) pour un appelant qui gère déjà sa propre fenêtre.
    """
    if user is None or not getattr(user, 'pk', None):
        return None
    if event_type not in EventType.values:
        logger.warning('notify(): type d\'événement inconnu %r', event_type)
        return None

    company = company if company is not None else getattr(user, 'company', None)

    # ODX23 — un événement d'un module ModuleToggle-OFF pour la société ne
    # notifie plus personne (no-op best-effort, même politique que
    # l'enforcement API ODX4). Whitelist fermée et partielle : voir
    # apps.notifications.module_gating.EVENT_MODULE.
    from .module_gating import event_module_disabled
    if event_module_disabled(event_type, company):
        return None

    prefs = resolve_prefs(user, event_type)
    from .models import NotificationReason
    reason = reason if reason in NotificationReason.values else ''
    quiet_now = _in_quiet_hours_non_critique(
        event_type, company, respect_quiet_hours)

    created = None
    if prefs.get('in_app'):
        try:
            created = Notification.objects.create(
                company=company, recipient=user, event_type=event_type,
                title=str(title)[:255], body=str(body or '')[:MAX_BODY_LEN],
                link=str(link or '')[:512], reason=reason)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Création notification in-app échouée : %s', exc)
            created = None
        else:
            _audit_notify(
                user, company, event_type, channel='in_app', ok=True,
                instance=created)

    if quiet_now:
        # VX209(a) — heures calmes : in-app livré ci-dessus, canaux hors-app
        # tus pour ce cycle (jamais de file d'attente/retry dans ce moteur —
        # comportement identique à un opt-out ponctuel du canal).
        return created

    # Diffusions hors-app : best-effort, chacune isolée.
    if prefs.get('email') and not skip_email:
        email_ok = False
        try:
            email_ok = _dispatch_email(user, str(title), str(body or ''))
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Dispatch email notification échoué : %s', exc)
        _audit_notify(
            user, company, event_type, channel='email', ok=email_ok,
            instance=created)
    if prefs.get('whatsapp'):
        wa_ok = False
        try:
            wa_ok = _dispatch_whatsapp(user, str(title), str(body or ''))
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('Dispatch WhatsApp notification échoué : %s', exc)
        _audit_notify(
            user, company, event_type, channel='whatsapp', ok=wa_ok,
            instance=created)

    # Web push (N92) : best-effort, opt-in par APPAREIL (pas un toggle
    # d'événement). NO-OP total sans clés VAPID ni abonnement — donc aucun
    # changement de comportement tant que rien n'est configuré.
    try:
        _dispatch_webpush(user, str(title), str(body or ''), link=link)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('Dispatch web push notification échoué : %s', exc)

    return created


# YEVNT5 — mapping canal → Action d'audit. 'in_app' n'a pas de valeur EMAIL/
# WHATSAPP dédiée dans AuditLog.Action → NOTIFY générique (ajoutée pour ce
# ticket). email/whatsapp réutilisent les actions EMAIL/WHATSAPP existantes,
# déjà utilisées ailleurs (PDF/génération de devis) pour rester cohérent.
_AUDIT_CHANNEL_ACTION = {
    'in_app': 'notify',
    'email': 'email',
    'whatsapp': 'whatsapp',
}


def _audit_notify(user, company, event_type, *, channel, ok, instance=None):
    """Écrit une ligne d'audit best-effort pour UN canal d'un envoi `notify()`.

    Ne bloque JAMAIS l'envoi : toute erreur d'écriture d'audit est absorbée
    par `audit.recorder.record` lui-même (best-effort), et on l'entoure ici
    d'une couche supplémentaire par prudence."""
    try:
        from apps.audit import recorder
        action = _AUDIT_CHANNEL_ACTION.get(channel, 'notify')
        statut = 'envoyé' if ok else 'échoué'
        detail = (
            f'Notification {event_type} → {channel} ({statut}) '
            f'destinataire={getattr(user, "username", user)}'
        )
        recorder.record(
            action, instance=instance, company=company,
            user=None,  # action système : le déclencheur n'est pas l'acteur HTTP.
            object_repr=str(instance) if instance is not None else str(event_type),
            detail=detail,
        )
    except Exception as exc:  # pragma: no cover - défensif
        logger.debug('audit_notify (canal %s) échoué : %s', channel, exc)


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


# =============================================================================
# XMKT25 — Cycle d'approbation Meta des gabarits WhatsApp BSP.
# =============================================================================

def approved_templates_for(company, *, event_key=None):
    """Gabarits WhatsApp SÉLECTIONNABLES pour une campagne (XMKT25).

    Seuls les gabarits `statut_approbation == APPROUVE` ET actifs sont
    proposables. `event_key` (optionnel) filtre par `groupe` — permet à un
    appelant de restreindre aux variantes fr/ar d'un même gabarit logique.
    Renvoie un QuerySet (peut être vide)."""
    from .models import WhatsAppTemplate
    qs = WhatsAppTemplate.objects.filter(
        company=company, active=True,
        statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE,
    )
    if event_key:
        qs = qs.filter(groupe=event_key)
    return qs.order_by('name', 'language')


def submit_template_for_approval(template, *, user=None):
    """Soumet un gabarit à l'approbation Meta (XMKT25), GATED sur credentials BSP.

    Sans `WHATSAPP_BSP_ENABLED=1` + credentials complets (même gate que
    `whatsapp_bsp.get_whatsapp_provider`), c'est un NO-OP FONCTIONNEL : le
    gabarit passe simplement en statut `soumis` pour que le statut soit saisi
    manuellement par la suite (l'ERP ne peut pas encore parler à l'API Meta).
    Idempotent : un gabarit déjà `approuve`/`rejete` n'est pas re-soumis (il
    faut d'abord le repasser en brouillon). Jamais d'exception remontée."""
    from .models import WhatsAppTemplate
    if template is None:
        return template
    if template.statut_approbation in (
            WhatsAppTemplate.StatutApprobation.APPROUVE,
            WhatsAppTemplate.StatutApprobation.REJETE):
        return template
    try:
        import os
        bsp_ready = os.getenv('WHATSAPP_BSP_ENABLED', '0') == '1' and all([
            os.getenv('WHATSAPP_BSP_BASE_URL', '').strip(),
            os.getenv('WHATSAPP_BSP_TOKEN', '').strip(),
            os.getenv('WHATSAPP_BSP_PHONE_NUMBER_ID', '').strip(),
        ])
        if bsp_ready:
            # SEAM : l'appel réel à l'API Meta de soumission de gabarit n'est
            # PAS implémenté (nécessite le compte Meta Business Manager du
            # fondateur). On marque quand même `soumis` pour que le statut
            # réel (approuvé/rejeté) soit saisi manuellement en retour de
            # Meta — comportement identique au chemin non-gated.
            logger.info(
                'submit_template_for_approval: BSP prêt mais soumission API '
                'Meta non implémentée (gabarit %s) — statut posé à "soumis" '
                'pour saisie manuelle du retour.', template.pk)
        template.statut_approbation = WhatsAppTemplate.StatutApprobation.SOUMIS
        template.save(update_fields=['statut_approbation', 'updated_at'])
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('submit_template_for_approval échoué (tpl %s) : %s',
                       getattr(template, 'pk', None), exc)
    return template


def set_template_approval_status(template, statut, *, motif_rejet=''):
    """Saisie MANUELLE du statut d'approbation (retour Meta lu par un humain).

    C'est le chemin normal tant que la soumission API n'est pas branchée :
    l'admin consulte le Meta Business Manager et reporte le statut ici.
    `statut` doit appartenir à `WhatsAppTemplate.StatutApprobation`."""
    from .models import WhatsAppTemplate
    if template is None:
        return template
    if statut not in WhatsAppTemplate.StatutApprobation.values:
        logger.warning('set_template_approval_status: statut inconnu %r', statut)
        return template
    template.statut_approbation = statut
    template.motif_rejet = (
        motif_rejet or '') if statut == WhatsAppTemplate.StatutApprobation.REJETE else ''
    template.save(update_fields=['statut_approbation', 'motif_rejet', 'updated_at'])
    return template


# =============================================================================
# XMKT10 — Canal WhatsApp dans les campagnes (opt-in, gated).
# =============================================================================

def render_whatsapp_template(template, *, prenom='', ville=''):
    """Substitue ``{prenom}``/``{ville}`` dans l'aide-mémoire du gabarit BSP
    (même convention que ``crm.MessageTemplate.render``). ``template`` peut
    être ``None`` (renvoie une chaîne vide) — l'appelant retombe alors sur le
    corps libre de la campagne."""
    if template is None:
        return ''
    return (template.body_fr or '').replace(
        '{prenom}', prenom or '').replace('{ville}', ville or '')


def send_whatsapp_campaign_message(company, *, recipient, body, campagne_id=None,
                                   template=None):
    """XMKT10 — envoie (ou prépare) UN message WhatsApp de campagne et le
    journalise TOUJOURS dans ``WhatsAppMessageLog``, lié à la campagne par
    ``campagne_id`` (référence opaque — ``notifications`` n'importe jamais
    ``apps.marketing``).

    Réutilise ``notifications.whatsapp_bsp.get_whatsapp_provider()`` (QJ23/
    FG33) : sans jeton BSP configuré, ``ManualWaMeProvider`` construit un lien
    wa.me — AUCUN appel réseau, comportement manuel actuel préservé à 100 %.
    Avec ``WHATSAPP_BSP_ENABLED=1`` + credentials complets, ``BspProvider``
    est utilisé (scaffold : retombe encore sur le lien manuel tant que
    ``_send_via_api`` n'est pas branché par le fondateur — voir whatsapp_bsp.py).

    Renvoie un dict ``{'log': WhatsAppMessageLog, 'url': str|None,
    'provider': 'manual'|'bsp'}``. Ne lève jamais d'exception (best-effort,
    comme ``notify()``). Ne journalise jamais ``prix_achat``/marge (appelant
    responsable du corps du message)."""
    from .models import WhatsAppMessageLog
    from .whatsapp_bsp import get_whatsapp_provider

    recipient = (recipient or '').strip()
    result = {'log': None, 'url': None, 'provider': 'manual'}
    if not recipient:
        return result
    try:
        provider = get_whatsapp_provider()
        wa_result = provider.get_wa_url(recipient, body or '')
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('send_whatsapp_campaign_message: provider échoué : %s', exc)
        wa_result = {'url': None, 'provider': 'manual'}
    provider_name = wa_result.get('provider') or 'manual'
    url = wa_result.get('url')
    is_bsp = provider_name == 'bsp'
    if is_bsp:
        status = WhatsAppMessageLog.Status.SENT
        provider_choice = WhatsAppMessageLog.Provider.BSP
    else:
        status = WhatsAppMessageLog.Status.MANUAL
        provider_choice = WhatsAppMessageLog.Provider.MANUAL
    try:
        log = WhatsAppMessageLog.objects.create(
            company=company, recipient=recipient, body=body or '',
            template=template,
            status=status,
            provider=provider_choice,
            campagne_id=campagne_id,
        )
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('send_whatsapp_campaign_message: log échoué : %s', exc)
        log = None
    result['log'] = log
    result['url'] = url
    result['provider'] = provider_name
    return result


# =============================================================================
# XKB5 — Annonces internes ciblées et programmées.
# =============================================================================

def _users_in_departement(company, departement_nom):
    """Utilisateurs de `company` rattachés (via `rh.DossierEmploye`) à un
    département dont le nom correspond (lecture seule, import function-local —
    jamais un FK cross-app dur, cf. CLAUDE.md). Best-effort : liste vide si
    l'app rh est indisponible ou si aucun match."""
    if not departement_nom:
        return []
    try:
        from apps.rh.models import DossierEmploye
        dossiers = DossierEmploye.objects.filter(
            company=company, departement__nom=departement_nom,
            user__isnull=False, user__is_active=True,
        ).select_related('user')
        return [d.user for d in dossiers if d.user_id]
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('_users_in_departement échoué : %s', exc)
        return []


def annonce_recipients(annonce):
    """Résout les destinataires d'une annonce selon son ciblage (XKB5).

    - TOUS : tous les utilisateurs actifs de la société.
    - ROLE : utilisateurs actifs avec ce `role_legacy`.
    - DEPARTEMENT : utilisateurs actifs rattachés (rh) à ce département.

    Best-effort : renvoie toujours un QuerySet/liste (jamais d'exception)."""
    from .models import Annonce
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        base = User.objects.filter(company=annonce.company, is_active=True)
        if annonce.cible_type == Annonce.Cible.ROLE:
            if not annonce.cible_role:
                return base.none()
            return base.filter(role_legacy=annonce.cible_role)
        if annonce.cible_type == Annonce.Cible.DEPARTEMENT:
            return _users_in_departement(
                annonce.company, annonce.cible_departement_nom)
        return base
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('annonce_recipients échoué (annonce %s) : %s',
                       getattr(annonce, 'pk', None), exc)
        from django.contrib.auth import get_user_model
        return get_user_model().objects.none()


def publish_annonce(annonce, *, now=None):
    """Publie une annonce (idempotent) : notifie les destinataires ciblés,
    marque `publiee=True` + `date_publication_effective`.

    Sans effet si déjà publiée. Best-effort : notifier chaque destinataire est
    isolé (une erreur n'empêche pas les suivants ni la publication elle-même)."""
    if annonce.publiee:
        return annonce
    now = now or timezone.now()
    recipients = annonce_recipients(annonce)
    link = '/annonces/' + str(annonce.pk)
    for user in recipients:
        try:
            notify(
                user, EventType.ANNONCE_PUBLISHED, annonce.titre,
                body=annonce.corps, link=link, company=annonce.company)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning('publish_annonce: notify échoué (user %s) : %s',
                           getattr(user, 'pk', None), exc)
    annonce.publiee = True
    annonce.date_publication_effective = now
    annonce.save(update_fields=['publiee', 'date_publication_effective'])
    return annonce


# =============================================================================
# XKB6 — Accusé de lecture obligatoire des annonces + rapport de conformité.
# =============================================================================

def acknowledge_annonce(annonce, user):
    """« J'ai lu et compris » : crée (idempotent) l'accusé de lecture de
    `user` pour `annonce`. Un second clic ne duplique rien (contrainte
    unique) et ne réinitialise pas `relances_envoyees`."""
    from .models import AnnonceLecture
    if annonce is None or user is None:
        return None
    lecture, _created = AnnonceLecture.objects.get_or_create(
        annonce=annonce, utilisateur=user,
        defaults={'company': annonce.company})
    return lecture


def annonce_compliance_report(annonce):
    """Rapport de conformité : qui a confirmé, quand, qui manque (XKB6).

    Ne s'applique qu'aux annonces `lecture_obligatoire=True` ET publiées —
    sinon la notion de « manquant » n'a pas de sens (renvoie des listes
    vides). `destinataires` = ceux ciblés par l'annonce au moment de l'appel
    (recalculé — le ciblage peut avoir changé depuis la publication)."""
    from .models import AnnonceLecture
    if not annonce.lecture_obligatoire or not annonce.publiee:
        return {'lus': [], 'manquants': [], 'total_cibles': 0}

    destinataires = list(annonce_recipients(annonce))
    lectures = {
        lc.utilisateur_id: lc
        for lc in AnnonceLecture.objects.filter(
            annonce=annonce).select_related('utilisateur')
    }
    lus = []
    manquants = []
    for user in destinataires:
        lecture = lectures.get(user.pk)
        if lecture is not None:
            lus.append({
                'user_id': user.pk,
                'username': getattr(user, 'username', ''),
                'date_lecture': lecture.date_lecture,
            })
        else:
            manquants.append({
                'user_id': user.pk,
                'username': getattr(user, 'username', ''),
            })
    return {
        'lus': lus, 'manquants': manquants,
        'total_cibles': len(destinataires),
    }


# Paliers de relance (jours ouvrés depuis la publication). Le premier palier
# relance le destinataire ; le second escalade vers les managers (mécanisme
# partagé avec YEVNT9, mais ici les « manquants » sont par LECTURE, pas par
# approbation).
ANNONCE_REMINDER_DELAY_DAYS = 2


def sweep_annonce_reminders(company, *, delay_days=None, today=None):
    """Relance les destinataires n'ayant pas confirmé une lecture obligatoire
    (XKB6), au-delà de `delay_days` jours ouvrés depuis la publication.

    Suit l'état de relance dans `AnnonceRelance` — JAMAIS dans
    `AnnonceLecture`, qui ne doit exister que pour une lecture réellement
    confirmée. Idempotent : au plus une relance par jour de balayage pour un
    même destinataire (`derniere_relance_le` comparée à `today`)."""
    from .calendar_utils import ajouter_jours_ouvres
    from .models import Annonce, AnnonceLecture, AnnonceRelance
    delay = delay_days if delay_days is not None else ANNONCE_REMINDER_DELAY_DAYS
    today = today or timezone.now().date()

    try:
        qs = Annonce.objects.filter(
            company=company, publiee=True, lecture_obligatoire=True)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('sweep_annonce_reminders: chargement annonces échoué : %s', exc)
        return 0

    count = 0
    for annonce in qs:
        try:
            if not annonce.date_publication_effective:
                continue
            due_date = ajouter_jours_ouvres(
                annonce.date_publication_effective.date(), delay, company)
            if due_date > today:
                continue
            destinataires = list(annonce_recipients(annonce))
            lu_ids = set(AnnonceLecture.objects.filter(
                annonce=annonce).values_list('utilisateur_id', flat=True))
            link = '/annonces/' + str(annonce.pk)
            for user in destinataires:
                if user.pk in lu_ids:
                    continue  # déjà lu → aucune relance.
                relance, _created = AnnonceRelance.objects.get_or_create(
                    annonce=annonce, utilisateur=user,
                    defaults={'company': company})
                if (relance.derniere_relance_le
                        and relance.derniere_relance_le.date() == today):
                    continue  # déjà relancé aujourd'hui → idempotent.
                notify(
                    user, EventType.ANNONCE_READ_REMINDER,
                    f"Lecture obligatoire en attente : {annonce.titre}",
                    body=annonce.corps, link=link, company=company)
                relance.relances_envoyees = (relance.relances_envoyees or 0) + 1
                relance.derniere_relance_le = timezone.now()
                relance.save(update_fields=[
                    'relances_envoyees', 'derniere_relance_le'])
                count += 1
        except Exception:  # pragma: no cover - défensif
            logger.warning('sweep_annonce_reminders: annonce %s échouée',
                           getattr(annonce, 'pk', None), exc_info=True)
    return count


# =============================================================================
# YEVNT9 — Relance/escalade des approbations en attente (les DEUX moteurs :
# automation.AutomationApproval + compta.DemandeApprobationConfig).
# =============================================================================

def approval_reminder_thresholds(company):
    """Seuils effectifs (relance_days, escalade_days) pour une société
    (config stockée, sinon défauts de classe). Best-effort."""
    from .models import ApprovalReminderConfig
    try:
        cfg = ApprovalReminderConfig.objects.filter(company=company).first()
        if cfg is not None:
            return (cfg.relance_days, cfg.escalade_days)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('approval_reminder_thresholds échoué : %s', exc)
    return (
        ApprovalReminderConfig.DEFAULT_RELANCE_DAYS,
        ApprovalReminderConfig.DEFAULT_ESCALADE_DAYS,
    )


def _approval_reminder_state(company, instance):
    """État de relance (créé si besoin) pour UNE approbation en attente,
    générique via content-type."""
    from django.contrib.contenttypes.models import ContentType

    from .models import ApprovalReminderState
    ct = ContentType.objects.get_for_model(instance.__class__)
    state, _created = ApprovalReminderState.objects.get_or_create(
        content_type=ct, object_id=instance.pk,
        defaults={'company': company})
    return state


def _sweep_one_pending_approval(company, instance, *, approver, requester,
                                link, description, relance_days,
                                escalade_days, today):
    """Traite UNE approbation en attente : relance au palier 1, escalade au
    palier 2 — jamais deux fois pour le même palier (état persisté).

    Renvoie 1 si une notification a été émise, 0 sinon."""
    from .calendar_utils import ajouter_jours_ouvres

    date_creation = getattr(instance, 'date_creation', None)
    if date_creation is None:
        return 0
    base_date = (
        date_creation.date() if hasattr(date_creation, 'date')
        else date_creation)
    relance_due = ajouter_jours_ouvres(base_date, relance_days, company)
    escalade_due = ajouter_jours_ouvres(base_date, escalade_days, company)

    state = _approval_reminder_state(company, instance)

    if state.palier < 2 and today >= escalade_due:
        from .sweeps import _managers
        title = "Approbation escaladée"
        body = f'{description} reste en attente depuis {escalade_days}+ jours ouvrés.'
        for admin in _managers(company):
            notify(admin, EventType.APPROVAL_ESCALATED, title, body=body,
                   link=link, company=company)
        state.palier = 2
        state.derniere_action_le = timezone.now()
        state.save(update_fields=['palier', 'derniere_action_le'])
        return 1

    if state.palier < 1 and today >= relance_due:
        if approver is not None:
            title = "Relance d'approbation"
            body = f'{description} attend toujours votre validation.'
            notify(approver, EventType.APPROVAL_REMINDER, title, body=body,
                   link=link, company=company)
        state.palier = 1
        state.derniere_action_le = timezone.now()
        state.save(update_fields=['palier', 'derniere_action_le'])
        return 1

    return 0


def sweep_approval_reminders(company, *, today=None):
    """Relance/escalade les approbations en attente au-delà des seuils
    (YEVNT9), pour les DEUX moteurs. Idempotent (un palier n'est jamais
    re-signalé) ; best-effort par approbation."""
    today = today or timezone.now().date()
    relance_days, escalade_days = approval_reminder_thresholds(company)
    count = 0

    try:
        from apps.automation.models import AutomationApproval
        pending = AutomationApproval.objects.filter(
            company=company, status=AutomationApproval.Status.PENDING
        ).select_related('rule', 'requested_by')
        for approval in pending:
            try:
                from .sweeps import _managers
                approvers = _managers(company)
                approver = approvers[0] if approvers else None
                count += _sweep_one_pending_approval(
                    company, approval, approver=approver,
                    requester=approval.requested_by,
                    link=f'/automation/approvals/{approval.pk}',
                    description=approval.description or 'Une action',
                    relance_days=relance_days, escalade_days=escalade_days,
                    today=today)
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'sweep_approval_reminders: automation approval %s échouée',
                    approval.pk, exc_info=True)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('sweep_approval_reminders: automation échoué : %s', exc)

    try:
        from apps.compta.models import DemandeApprobationConfig
        pending = DemandeApprobationConfig.objects.filter(
            company=company,
            statut=DemandeApprobationConfig.Statut.EN_ATTENTE,
        ).select_related('demandeur')
        for demande in pending:
            try:
                from .sweeps import _managers
                approvers = _managers(company)
                approver = approvers[0] if approvers else None
                label = demande.devis_reference or demande.devis_id or ''
                count += _sweep_one_pending_approval(
                    company, demande, approver=approver,
                    requester=demande.demandeur,
                    link=f'/compta/approbations/{demande.pk}',
                    description=f'La demande {label}',
                    relance_days=relance_days, escalade_days=escalade_days,
                    today=today)
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'sweep_approval_reminders: demande approbation %s échouée',
                    demande.pk, exc_info=True)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('sweep_approval_reminders: compta échoué : %s', exc)

    return count


# =============================================================================
# VX210(b) — snooze GÉNÉRIQUE d'un item d'approbation (SnoozedItem).
# Écriture EXCLUSIVEMENT via ces deux fonctions — jamais un import direct de
# `SnoozedItem` par un appelant cross-app (ex. `apps.records.views`).
# =============================================================================

def snooze_approbation_item(company, user, source, object_id, snoozed_until):
    """Snooze/upsert un item d'approbation hétérogène (5 sources de
    ``reporting.approbations``) jusqu'à ``snoozed_until`` pour ``user``.
    Idempotent (une ligne existante est mise à jour, pas dupliquée)."""
    from .models import SnoozedItem
    obj, _created = SnoozedItem.objects.update_or_create(
        user=user, source=source, object_id=object_id,
        defaults={'company': company, 'snoozed_until': snoozed_until})
    return obj


def unsnooze_approbation_item(user, source, object_id):
    """Annule le snooze d'un item d'approbation (redevient visible dans « Ma
    file » immédiatement). No-op silencieux si rien n'était snoozé."""
    from .models import SnoozedItem
    SnoozedItem.objects.filter(
        user=user, source=source, object_id=object_id).delete()
