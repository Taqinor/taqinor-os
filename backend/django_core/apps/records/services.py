"""Services (écritures/orchestration) de `records` — XKB34 (followers).

`records` est une app de FONDATION : ce module n'importe jamais une app
métier (crm/ventes/stock/installations/sav). Les diffusions vers
`apps.notifications` (satellite) restent des imports fonction-locaux et
best-effort — jamais d'exception remontée à l'appelant — exactement comme le
fait déjà `views._notify_mentions` pour les @mentions du chatter (FG7).
"""
from .models import Follower


def follow(*, company, content_type, object_id, user, sous_type=''):
    """Abonne `user` à l'enregistrement (content_type, object_id).

    Idempotent : suivre deux fois la même cible (même `sous_type`) ne crée
    qu'un seul `Follower` (`get_or_create`).
    """
    obj, _created = Follower.objects.get_or_create(
        company=company, content_type=content_type, object_id=object_id,
        user=user, sous_type=sous_type)
    return obj


def unfollow(*, content_type, object_id, user, sous_type=''):
    """Désabonne `user` de la cible. No-op si l'abonnement n'existe pas."""
    Follower.objects.filter(
        content_type=content_type, object_id=object_id, user=user,
        sous_type=sous_type).delete()


def is_following(*, content_type, object_id, user):
    return Follower.objects.filter(
        content_type=content_type, object_id=object_id, user=user).exists()


def auto_follow(*, company, content_type, object_id, user, sous_type=''):
    """Auto-abonnement à l'assignation (XKB34) — même mécanisme que `follow`.

    Destiné à être appelé par le code d'assignation de l'app propriétaire de
    la cible (ex. `crm` à l'affectation d'un `owner` de lead) : `records` ne
    connaît jamais la cible métier au-delà de son `ContentType`/`object_id`,
    donc l'appel reste à l'initiative de l'app métier — jamais l'inverse.
    """
    return follow(company=company, content_type=content_type,
                  object_id=object_id, user=user, sous_type=sous_type)


def notify_followers(*, content_type, object_id, title, body='',
                     exclude_user=None, sous_type=None):
    """Notifie tous les followers d'une cible (note de chatter, XKB34).

    `sous_type` : si fourni, ne notifie que les abonnements SANS filtre
    (`sous_type=''`, "tout") OU dont le filtre correspond exactement (ex. les
    followers `'etape'` ne sont notifiés que sur un changement d'étape). Si
    omis (None), notifie tous les followers de la cible sans distinction.
    Best-effort : une notification qui échoue n'empêche jamais les autres, et
    n'échoue jamais l'appelant (import fonction-local, satellite optionnel).
    """
    qs = Follower.objects.filter(
        content_type=content_type, object_id=object_id
    ).select_related('user', 'company')
    if sous_type is not None:
        qs = qs.filter(sous_type__in=('', sous_type))
    if exclude_user is not None:
        qs = qs.exclude(user=exclude_user)

    try:
        from apps.notifications.models import EventType as ET
        from apps.notifications.services import notify
    except Exception:  # pragma: no cover - défensif
        return 0

    sent = 0
    for f in qs:
        try:
            notify(f.user, ET.CHAT_MENTION, title, body=body,
                   company=f.company)
            sent += 1
        except Exception:  # pragma: no cover - défensif
            continue
    return sent
