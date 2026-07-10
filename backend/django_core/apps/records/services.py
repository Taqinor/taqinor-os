"""Services (écritures/orchestration) de `records` — XKB34 (followers).

`records` est une app de FONDATION : ce module n'importe jamais une app
métier (crm/ventes/stock/installations/sav). Les diffusions vers
`apps.notifications` (satellite) restent des imports fonction-locaux et
best-effort — jamais d'exception remontée à l'appelant — exactement comme le
fait déjà `views._notify_mentions` pour les @mentions du chatter (FG7).
"""
from .models import Activity, Follower


def log_activity(target, kind, *, user=None, field='', field_label='',
                 old_value='', new_value='', body='', company=None):
    """ARC8 — écrit UNE entrée de chatter générique (`records.Activity`).

    Le « mail.thread » maison : convergence des 13 modèles ``*Activity``
    quasi identiques (kind/field/old/new/body/user/timestamp). Ce service est
    le SEUL point d'écriture du chatter générique ; il pose la société et
    l'utilisateur CÔTÉ SERVEUR (jamais lus du corps de requête).

    Args:
        target: instance métier cible (Contrat, Vehicule…). Sa société est
            déduite via ``target.company`` si ``company`` n'est pas fourni.
        kind: valeur de ``Activity.Kind`` (``note`` / ``modification`` /
            ``creation``).
        user: auteur (``request.user``), toujours posé côté serveur.
        field / field_label / old_value / new_value: instantané d'un changement
            de champ (pour un journal automatique ``kind=modification``).
        body: texte libre (pour une note manuelle ``kind=note``).
        company: société explicite ; par défaut ``target.company``.

    `records` est une app de FONDATION : on ne connaît la cible qu'à travers son
    ``ContentType`` (jamais d'import d'une app métier).
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(target.__class__)
    if company is None:
        company = getattr(target, 'company', None)
    return Activity.objects.create(
        company=company,
        content_type=ct,
        object_id=target.pk,
        activity_type=None,
        kind=kind,
        field=field or '',
        field_label=field_label or '',
        old_value=old_value or '',
        new_value=new_value or '',
        body=body or '',
        created_by=user,
    )


def log_note(target, user, body, *, company=None):
    """ARC8 — raccourci : note manuelle de chatter (``kind=note``)."""
    return log_activity(
        target, Activity.Kind.NOTE, user=user, body=body, company=company)


def chatter_qs(target, company=None):
    """ARC8 — timeline du chatter générique d'une cible (plus récent d'abord).

    Ne renvoie QUE les entrées de chatter (``kind`` renseigné) — jamais les
    activités planifiées (``kind`` vide) de la même cible. Scopé société si
    fournie."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(target.__class__)
    qs = Activity.objects.filter(
        content_type=ct, object_id=target.pk).exclude(kind='')
    if company is not None:
        qs = qs.filter(company=company)
    return qs.select_related('created_by').order_by('-created_at', '-id')


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
