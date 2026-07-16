"""Services (écritures/orchestration) de `records` — XKB34 (followers).

`records` est une app de FONDATION : ce module n'importe jamais les
`models`/`views` d'une app métier (crm/ventes/stock/installations/sav) — les
QUELQUES lectures cross-app nécessaires (VX210(c), voir
`_trigger_event_survenu` ci-dessous) passent EXCLUSIVEMENT par le
`selectors.py` PUBLIC de l'app cible (même contrat que `reporting.
approbations` qui lit 5 apps métier via leurs selectors), jamais un import
direct de ses `models`. Les diffusions vers `apps.notifications` (satellite)
restent des imports fonction-locaux et best-effort — jamais d'exception
remontée à l'appelant — exactement comme le fait déjà `views._notify_mentions`
pour les @mentions du chatter (FG7).
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


def log_field_change(target, field, old_value, new_value, *, user=None,
                     field_label='', company=None):
    """ARC16 — raccourci : entrée de chatter « modification » d'un champ.

    Point d'entrée côté ``records`` utilisé par l'entonnoir de journalisation
    ``apps.audit.recorder.record_field_change`` (qui écrit l'``AuditLog`` ET
    cette ligne de chatter en un seul appel). Reste purement additif : c'est un
    simple raccourci sur ``log_activity`` avec ``kind=modification`` — la société
    et l'auteur restent posés côté serveur.
    """
    return log_activity(
        target, Activity.Kind.MODIFICATION, user=user, field=field or '',
        field_label=field_label or '', old_value=old_value,
        new_value=new_value, company=company)


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
                     exclude_user=None, sous_type=None, link=None):
    """Notifie tous les followers d'une cible (note de chatter, XKB34).

    `sous_type` : si fourni, ne notifie que les abonnements SANS filtre
    (`sous_type=''`, "tout") OU dont le filtre correspond exactement (ex. les
    followers `'etape'` ne sont notifiés que sur un changement d'étape). Si
    omis (None), notifie tous les followers de la cible sans distinction.
    `link` (VX85(b)) : lien profond optionnel transmis tel quel à `notify()`
    (None par défaut — comportement inchangé pour les appelants existants).
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
            # VX212(a) — « pourquoi je reçois ça » : cette diffusion vient
            # TOUJOURS d'un abonnement (`Follower`), jamais d'une autre voie.
            notify(f.user, ET.CHAT_MENTION, title, body=body,
                   link=link, company=f.company, reason='vous_suivez')
            sent += 1
        except Exception:  # pragma: no cover - défensif
            continue
    return sent


# =============================================================================
# VX210 — le snooze devient un rappel ACTIF, généralisé, et déclenché par
# l'événement métier. VX85 pose `snoozed_until` + exclusion passive : rien ne
# RÉVEILLE l'item ni ne re-notifie à l'échéance — c'est ce que ce module
# ajoute.
# =============================================================================

# VX210(c) — préfixes FERMÉS de `snooze_trigger_event` (« <préfixe>:<id> »).
# On n'invente jamais un déclencheur à la volée : en ajouter un = une ligne
# ici + un cas dans `_trigger_event_survenu`.
TRIGGER_CLIENT_REPLY = 'client_reply'
TRIGGER_DEVIS_SIGNED = 'devis_signed'
TRIGGER_STOCK_ARRIVE = 'stock_arrive'
SNOOZE_TRIGGER_PREFIXES = frozenset({
    TRIGGER_CLIENT_REPLY, TRIGGER_DEVIS_SIGNED, TRIGGER_STOCK_ARRIVE,
})


def valid_snooze_trigger_event(value):
    """VX210(c) — valide le format fermé ``<préfixe>:<id>`` (chaîne vide =
    aucun déclencheur, toujours valide — comportement VX85 inchangé)."""
    value = (value or '').strip()
    if not value:
        return True
    prefix, sep, rest = value.partition(':')
    return sep == ':' and prefix in SNOOZE_TRIGGER_PREFIXES and rest.strip() != ''


def _trigger_event_survenu(trigger_event, company, since):
    """VX210(c) — True si `trigger_event` (« préfixe:id ») est DÉJÀ survenu
    depuis `since` (l'horodatage de pose du snooze, `Activity.snoozed_at`).

    Lecture EXCLUSIVEMENT via le `selectors.py` PUBLIC de l'app cible (jamais
    un import de ses `models` — même contrat cross-app que `reporting.
    approbations`). Best-effort strict : toute app absente/erreur/argument
    invalide renvoie ``False`` — un item ne se réveille JAMAIS à tort."""
    if not trigger_event or since is None or company is None:
        return False
    prefix, _, raw_id = trigger_event.partition(':')
    try:
        target_id = int(raw_id)
    except (TypeError, ValueError):
        return False
    try:
        if prefix == TRIGGER_CLIENT_REPLY:
            from apps.crm import selectors as crm_selectors
            lead = crm_selectors.get_company_lead(company, target_id)
            if lead is None:
                return False
            for entry in crm_selectors.lead_chatter_envelope(lead):
                created = entry.get('created_at')
                if created and created > since:
                    return True
            return False
        if prefix == TRIGGER_DEVIS_SIGNED:
            from apps.ventes import selectors as ventes_selectors
            devis = ventes_selectors.get_devis_by_pk(target_id)
            if devis is None or devis.company_id != company.id:
                return False
            return bool(ventes_selectors.is_devis_accepte(devis))
        if prefix == TRIGGER_STOCK_ARRIVE:
            from apps.stock import selectors as stock_selectors
            produit = stock_selectors.get_produit_scoped(company, target_id)
            return bool(produit and produit.quantite_stock > 0)
    except Exception:  # pragma: no cover - défensif, ne réveille jamais à tort
        return False
    return False


def _notifier_reveil_activite(activity):
    """VX210(a) — notification LÉGÈRE « ⏰ De retour » au propriétaire d'une
    activité réveillée. Best-effort, jamais une exception remontée (même
    convention que `notify_followers`)."""
    if activity.assigned_to_id is None:
        return
    try:
        from apps.notifications.models import EventType as ET
        from apps.notifications.services import notify
        link = None
        if activity.content_type_id and activity.object_id:
            label = f'{activity.content_type.app_label}.{activity.content_type.model}'
            if label == 'crm.lead':
                link = f'/crm/leads?lead={activity.object_id}'
            elif label == 'crm.client':
                link = '/crm'
            elif label == 'installations.installation':
                link = '/chantiers'
            elif label == 'sav.ticket':
                link = '/sav'
        notify(
            activity.assigned_to, ET.SNOOZE_REVEIL,
            f'⏰ De retour : {activity.summary or "Activité"}',
            link=link, company=activity.company)
    except Exception:  # pragma: no cover - défensif
        pass


def snooze_activity(activity, snoozed_until, trigger_event=''):
    """VX210 — pose (ou annule) le snooze d'une activité, avec son
    déclencheur optionnel (VX210(c)). Raccourci utilisé par la vue ; horodate
    `snoozed_at` à la pose (borne « depuis » de `_trigger_event_survenu`)."""
    from django.utils import timezone
    if snoozed_until:
        activity.snoozed_until = snoozed_until
        activity.snooze_trigger_event = trigger_event or ''
        activity.snoozed_at = timezone.now()
    else:
        activity.snoozed_until = None
        activity.snooze_trigger_event = ''
        activity.snoozed_at = None
    activity.save(update_fields=[
        'snoozed_until', 'snooze_trigger_event', 'snoozed_at'])
    return activity


def reveiller_snoozes(company):
    """VX210(a)/(c) — sweep : réveille chaque `Activity` de `company` dont
    `snoozed_until` est échu OU dont `snooze_trigger_event` est DÉJÀ survenu
    (le premier des deux gagne). Nettoie les deux champs (idempotent — un item
    déjà réveillé ne peut plus re-matcher) et notifie légèrement son
    propriétaire. Renvoie le nombre d'items réveillés."""
    from django.utils import timezone

    today = timezone.now().date()
    qs = Activity.objects.filter(company=company).exclude(
        snoozed_until__isnull=True, snooze_trigger_event='')
    woken = 0
    for act in qs.select_related('assigned_to', 'company', 'content_type'):
        due = act.snoozed_until is not None and act.snoozed_until <= today
        triggered = False
        if not due and act.snooze_trigger_event:
            triggered = _trigger_event_survenu(
                act.snooze_trigger_event, act.company, act.snoozed_at)
        if not (due or triggered):
            continue
        act.snoozed_until = None
        act.snooze_trigger_event = ''
        act.snoozed_at = None
        act.save(update_fields=[
            'snoozed_until', 'snooze_trigger_event', 'snoozed_at'])
        _notifier_reveil_activite(act)
        woken += 1
    return woken
