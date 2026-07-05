"""Orchestration de la messagerie interne (écritures + logique transverse).

Tout passe par la société de l'appelant, jamais par le corps de requête. Les
lectures cross-app (cartes lead/devis/chantier) passent par les `selectors.py`
des apps cibles — jamais par leurs modèles/vues (contrat d'import CI).
"""
import re

from django.db import transaction
from django.utils import timezone


# ── Résolution d'une carte d'enregistrement partagé (S8) ──────────────
# Mappe un type lisible vers le sélecteur LECTURE SEULE de l'app cible. On
# n'importe JAMAIS les modèles/vues d'une autre app ici.
def _record_card(record_type, record_id, company):
    rt = (record_type or '').strip().lower()
    if rt == 'lead':
        from apps.crm.selectors import lead_card
        return lead_card(record_id, company)
    if rt == 'devis':
        from apps.ventes.selectors import devis_card
        return devis_card(record_id, company)
    if rt in ('chantier', 'installation'):
        from apps.installations.selectors import chantier_card
        return chantier_card(record_id, company)
    return None


def _content_type_for(record_type):
    from django.contrib.contenttypes.models import ContentType
    rt = (record_type or '').strip().lower()
    mapping = {
        'lead': ('crm', 'lead'),
        'devis': ('ventes', 'devis'),
        'chantier': ('installations', 'installation'),
        'installation': ('installations', 'installation'),
    }
    pair = mapping.get(rt)
    if not pair:
        return None
    app_label, model = pair
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:  # pragma: no cover - défensif
        return None


# ── Détection des @mentions dans un corps de texte ────────────────────
_MENTION_RE = re.compile(r'@([\w.\-]+)')


def _resolve_mentions(conversation, body):
    """Retourne les membres mentionnés (@username/@email) présents dans la
    conversation. On ne mentionne que des MEMBRES de la conversation."""
    if not body:
        return []
    handles = {h.lower() for h in _MENTION_RE.findall(body)}
    if not handles:
        return []
    from .models import ConversationMember
    members = ConversationMember.objects.filter(
        conversation=conversation).select_related('user')
    hit = []
    for m in members:
        u = m.user
        if u is None:
            continue
        candidates = {
            (getattr(u, 'username', '') or '').lower(),
            (getattr(u, 'email', '') or '').lower(),
            (getattr(u, 'email', '') or '').split('@')[0].lower(),
        }
        if candidates & handles:
            hit.append(u)
    return hit


def _members_by_ids(conversation, ids):
    """Membres de la conversation dont l'id figure dans `ids` (S16).

    On ne mentionne JAMAIS un utilisateur qui n'est pas membre : la liste
    fournie par le client est filtrée à l'appartenance, côté serveur."""
    wanted = {int(i) for i in (ids or []) if str(i).isdigit()}
    if not wanted:
        return []
    from .models import ConversationMember
    return [
        m.user for m in ConversationMember.objects.filter(
            conversation=conversation, user_id__in=wanted)
        .select_related('user')
        if m.user is not None
    ]


@transaction.atomic
def create_message(*, conversation, sender, company, body='', kind=None,
                   reply_to=None, record_type=None, record_id=None,
                   mention_ids=None, skip_channel_notify=False):
    """Crée un message dans une conversation (membre déjà vérifié en amont).

    Gère le partage d'enregistrement (S8) et les @mentions (S9). La société est
    TOUJOURS celle de la conversation/appelant. Lève ValueError si un
    enregistrement partagé n'appartient pas à la société.

    Les @mentions sont résolues depuis le corps (@username/@email) ET, en plus,
    depuis la liste d'ids `mention_ids` fournie par le client (S16) — toujours
    filtrée à l'appartenance, jamais cross-conversation.

    `skip_channel_notify` (XKB24) : les réponses en fil notifient UNIQUEMENT les
    suiveurs du fil (`_notify_thread_followers`), jamais le fan-out S9 tout-canal."""
    from .models import Message, MessageMention

    shared_ct = None
    shared_label = ''
    if record_type and record_id:
        card = _record_card(record_type, record_id, company)
        if card is None:
            raise ValueError(
                "Enregistrement introuvable ou hors de votre société.")
        shared_ct = _content_type_for(record_type)
        subtitle = card.get('subtitle') or ''
        shared_label = (
            f"{card.get('label', '')} — {subtitle}".strip(' —')
            if subtitle else card.get('label', ''))
        kind = Message.Kind.RECORD

    msg = Message.objects.create(
        company=company,
        conversation=conversation,
        sender=sender,
        body=body or '',
        kind=kind or Message.Kind.TEXT,
        reply_to=reply_to,
        shared_content_type=shared_ct,
        shared_object_id=(int(record_id) if (shared_ct and record_id)
                          else None),
        shared_label=shared_label,
    )

    # Touche la conversation pour le tri par activité récente.
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=['updated_at'])

    # @mentions → lignes dédiées (push plus fort). On unionne les mentions
    # détectées dans le texte et celles explicitement fournies par le client.
    mentioned_map = {u.pk: u for u in _resolve_mentions(conversation, body)}
    for u in _members_by_ids(conversation, mention_ids):
        mentioned_map[u.pk] = u
    mentioned = list(mentioned_map.values())
    for u in mentioned:
        MessageMention.objects.get_or_create(message=msg, mentioned_user=u)

    # Notifications (in-app + Web Push), best-effort, après commit. XKB24 : une
    # réponse en fil notifie uniquement ses suiveurs (cf. reply_in_thread) —
    # jamais le fan-out S9 tout-canal.
    if not skip_channel_notify:
        transaction.on_commit(lambda: _notify_new_message(msg, mentioned))
    # ZCTR12 — canal aliasé -> fan-out email aux membres opt-in (NO-OP sans
    # alias/config email, jamais bloquant).
    transaction.on_commit(lambda: notify_channel_alias_email(msg))
    return msg


def _notify_new_message(message, mentioned_users):
    """S9 — notifie les autres membres selon leur niveau de notification ;
    @mention = plus fort.

    Réutilise le point d'entrée `notify()` (in-app + Web Push). Respecte les
    préférences utilisateur ET le niveau PAR CONVERSATION (XKB25 : tout /
    mentions seulement / muet — l'existant `is_muted` reste préservé, il est
    mappé vers `muted`)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
    except Exception:  # pragma: no cover - défensif
        return

    from .models import ConversationMember

    conv = message.conversation
    sender = message.sender
    company = message.company
    mentioned_ids = {u.pk for u in (mentioned_users or []) if u is not None}

    title = _conversation_title(conv, sender)
    preview = _preview(message)
    link = f'/messages/{conv.pk}'

    members = (ConversationMember.objects
               .filter(conversation=conv)
               .exclude(is_muted=True)
               .exclude(notification_level=ConversationMember.NotificationLevel.MUTED)
               .select_related('user'))
    for m in members:
        u = m.user
        if u is None or (sender is not None and u.pk == sender.pk):
            continue
        is_mention = u.pk in mentioned_ids
        # « Mentions seulement » : seuls les CHAT_MENTION passent.
        if (m.notification_level == ConversationMember.NotificationLevel.MENTIONS
                and not is_mention):
            continue
        # XKB26 — Ne pas déranger : supprime le push/notification chat NON
        # URGENTE pendant la fenêtre (une @mention reste chat, pas "urgente"
        # au sens métier — seule une future alerte critique passerait le NPD ;
        # ici on suit la spec : NPD supprime le push chat pendant la fenêtre).
        if _is_user_dnd_active(u.pk):
            continue
        if is_mention:
            event = EventType.CHAT_MENTION
            ntitle = f'{title} vous a mentionné'
        else:
            event = EventType.CHAT_MESSAGE
            ntitle = title
        try:
            notify(u, event, ntitle, body=preview, link=link, company=company)
        except Exception:  # pragma: no cover - défensif
            continue


# ── XKB25 — niveau de notification par conversation ───────────────────

def set_notification_level(member, level):
    """Applique un niveau de notification à un `ConversationMember`, en
    synchronisant `is_muted` pour compat ascendante (tout code lisant encore
    `is_muted` voit `True` uniquement quand le niveau est `muted`)."""
    from .models import ConversationMember
    valid = dict(ConversationMember.NotificationLevel.choices)
    if level not in valid:
        raise ValueError('Niveau de notification invalide.')
    member.notification_level = level
    member.is_muted = (level == ConversationMember.NotificationLevel.MUTED)
    member.save(update_fields=['notification_level', 'is_muted'])
    return member


# ── XKB26 — statut personnalisé & Ne pas déranger ──────────────────────

def _is_user_dnd_active(user_id):
    """Best-effort : vrai si l'utilisateur `user_id` est actuellement en NPD."""
    from .models import UserChatStatus
    st = UserChatStatus.objects.filter(user_id=user_id).first()
    if st is None:
        return False
    return st.is_dnd_active()


def get_or_create_status(user, company):
    from .models import UserChatStatus
    st, _ = UserChatStatus.objects.get_or_create(
        user=user, defaults={'company': company})
    return st


def set_status(user, company, *, status_text=None, status_emoji=None):
    """Pose un statut (texte + emoji) visible par les collègues."""
    st = get_or_create_status(user, company)
    fields = []
    if status_text is not None:
        st.status_text = status_text[:120]
        fields.append('status_text')
    if status_emoji is not None:
        st.status_emoji = status_emoji[:16]
        fields.append('status_emoji')
    if fields:
        st.save(update_fields=fields)
    return st


def clear_status(user, company):
    return set_status(user, company, status_text='', status_emoji='')


def set_dnd(user, company, *, start, end):
    """Pose la fenêtre NPD (début/fin) — supprime push/notifications chat non
    urgentes pendant cette fenêtre (voir `_notify_new_message`)."""
    if start is not None and end is not None and end <= start:
        raise ValueError('La fin du NPD doit être après le début.')
    st = get_or_create_status(user, company)
    st.dnd_start = start
    st.dnd_end = end
    st.save(update_fields=['dnd_start', 'dnd_end'])
    return st


def clear_dnd(user, company):
    return set_dnd(user, company, start=None, end=None)


def touch_last_seen(user, company):
    """« Vu récemment » best-effort — appelé depuis le polling existant (S4
    unread/list), jamais via WebSocket."""
    st = get_or_create_status(user, company)
    st.last_seen_at = timezone.now()
    st.save(update_fields=['last_seen_at'])
    return st


def colleague_statuses(company, user_ids=None):
    """Statuts des collègues de la société (liste conversations / autocomplete
    @mention) — scopé société, jamais cross-tenant."""
    from .models import UserChatStatus
    qs = UserChatStatus.objects.filter(company=company).select_related('user')
    if user_ids:
        qs = qs.filter(user_id__in=user_ids)
    now = timezone.now()
    out = []
    for st in qs:
        out.append({
            'user_id': st.user_id,
            'status_text': st.status_text,
            'status_emoji': st.status_emoji,
            'is_dnd': st.is_dnd_active(now),
            'last_seen_at': st.last_seen_at,
        })
    return out


def _conversation_title(conversation, sender):
    sender_name = ''
    if sender is not None:
        sender_name = (getattr(sender, 'get_full_name', lambda: '')()
                       or getattr(sender, 'username', '') or '')
    if conversation.kind == conversation.Kind.CHANNEL and conversation.name:
        base = f'#{conversation.name}'
        return f'{sender_name} dans {base}' if sender_name else base
    return sender_name or 'Nouveau message'


def _preview(message):
    if message.shared_label:
        return f'📎 {message.shared_label}'[:200]
    if message.kind == message.Kind.VOICE:
        return '🎤 Mémo vocal'
    if message.body:
        return message.body[:200]
    return 'Pièce jointe'


# ── Transcription des mémos vocaux (S11) ──────────────────────────────
def enqueue_voice_transcription(attachment_id):
    """Enfile la transcription d'un mémo vocal APRÈS commit de la pièce.

    Appelé par le signal `post_save` sur `MessageAttachment` (signals.py). On
    diffère via `transaction.on_commit` pour que le worker ne lise pas une pièce
    encore invisible (transaction en cours). Best-effort : si le broker est
    indisponible, on n'interrompt jamais l'upload (la pièce restera `pending` et
    pourra être relancée). NO-OP quand la transcription est désactivée — la tâche
    elle-même bascule alors la pièce en `disabled`."""
    def _send():
        try:
            from .tasks import task_transcribe_voice_attachment
            task_transcribe_voice_attachment.delay(attachment_id)
        except Exception:  # pragma: no cover - broker indisponible
            pass

    transaction.on_commit(_send)


# ── Lecture / non-lus (S4) ────────────────────────────────────────────
def mark_read(conversation, user, when=None):
    """Avance `last_read_at` du membre à `when` (par défaut maintenant)."""
    from .models import ConversationMember
    when = when or timezone.now()
    updated = ConversationMember.objects.filter(
        conversation=conversation, user=user).update(last_read_at=when)
    return updated > 0


def unread_count(conversation, member):
    """Nombre de messages non lus (créés après `last_read_at`, hors les siens,
    hors supprimés) pour ce membre dans cette conversation."""
    from .models import Message
    qs = Message.objects.filter(
        conversation=conversation, deleted_at__isnull=True)
    if member.last_read_at is not None:
        qs = qs.filter(created_at__gt=member.last_read_at)
    if member.user_id is not None:
        qs = qs.exclude(sender_id=member.user_id)
    return qs.count()


def unread_summary(user, company):
    """Map {conversation_id: unread} + total, pour le badge d'en-tête.

    Une seule passe : pour chaque appartenance, compte les messages plus récents
    que `last_read_at`, hors ses propres messages et supprimés."""
    from .models import ConversationMember, Message

    memberships = list(
        ConversationMember.objects.filter(
            user=user, conversation__company=company)
        .select_related('conversation'))
    per_conv = {}
    total = 0
    for m in memberships:
        qs = Message.objects.filter(
            conversation_id=m.conversation_id, deleted_at__isnull=True)
        if m.last_read_at is not None:
            qs = qs.filter(created_at__gt=m.last_read_at)
        qs = qs.exclude(sender_id=user.pk)
        c = qs.count()
        per_conv[m.conversation_id] = c
        total += c
    return {'per_conversation': per_conv, 'total': total}


# ── XKB33 — Conversation dédiée « WhatsApp — <contact> » ────────────────────

def get_or_create_whatsapp_conversation(company, contact_label):
    """Canal dédié « WhatsApp — <contact> » pour un numéro entrant (XKB33).

    Point d'entrée cross-app sanctionné pour `apps.notifications` (webhook BSP
    WhatsApp) : jamais d'import direct des modèles chat depuis notifications.
    Idempotent PAR (company, nom) : un même contact reste dans le même canal.
    Tous les managers actifs (admin/responsable) de la société sont membres,
    pour que l'équipe voie la conversation. Best-effort : renvoie None en cas
    d'erreur, ne lève jamais."""
    from django.contrib.auth import get_user_model

    from .models import Conversation, ConversationMember

    try:
        name = f'WhatsApp — {contact_label}'[:255]
        conv, created = Conversation.objects.get_or_create(
            company=company, kind=Conversation.Kind.CHANNEL, name=name)
        if created:
            User = get_user_model()
            managers = User.objects.filter(
                company=company, is_active=True,
                role_legacy__in=['admin', 'responsable'])
            for user in managers:
                ConversationMember.objects.get_or_create(
                    conversation=conv, user=user)
        return conv
    except Exception:  # noqa: BLE001 — jamais bloquant pour le webhook
        return None


# ── XKB24 — Fils de discussion ────────────────────────────────────────

@transaction.atomic
def reply_in_thread(*, root_message, sender, company, body='', **kwargs):
    """Poste une réponse en fil sur `root_message` (XKB24).

    Auto-suit le fil pour l'auteur racine ET le répondant (`ThreadFollow`), puis
    notifie UNIQUEMENT les autres suiveurs du fil (jamais tout le canal) — via
    `EventType.CHAT_MESSAGE`/`CHAT_MENTION` déjà utilisés par le fan-out S9.
    """
    from .models import ThreadFollow

    reply = create_message(
        conversation=root_message.conversation, sender=sender, company=company,
        body=body, reply_to=root_message, skip_channel_notify=True, **kwargs)

    # Auto-suivi : le premier posteur (racine) et chaque répondant.
    if root_message.sender_id:
        ThreadFollow.objects.get_or_create(
            root_message=root_message, user_id=root_message.sender_id)
    if sender is not None:
        ThreadFollow.objects.get_or_create(
            root_message=root_message, user=sender)

    transaction.on_commit(lambda: _notify_thread_followers(root_message, reply, sender))
    return reply


def _notify_thread_followers(root_message, reply, sender):
    """Notifie les suiveurs du fil (hors auteur de la réponse), jamais le canal
    entier — best-effort, jamais bloquant."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
    except Exception:  # pragma: no cover - défensif
        return

    from .models import ThreadFollow

    title = 'Nouvelle réponse dans un fil que vous suivez'
    preview = _preview(reply)
    link = f'/messages/{root_message.conversation_id}?thread={root_message.pk}'

    followers = (ThreadFollow.objects
                 .filter(root_message=root_message)
                 .select_related('user'))
    for f in followers:
        u = f.user
        if u is None or (sender is not None and u.pk == sender.pk):
            continue
        try:
            notify(u, EventType.CHAT_MESSAGE, title, body=preview, link=link,
                   company=reply.company)
        except Exception:  # pragma: no cover - défensif
            continue


def thread_reply_count(root_message):
    """Nombre de réponses (non supprimées) dans le fil de `root_message`."""
    return root_message.replies.filter(deleted_at__isnull=True).count()


def follow_thread(root_message, user):
    from .models import ThreadFollow
    obj, _ = ThreadFollow.objects.get_or_create(
        root_message=root_message, user=user)
    return obj


def unfollow_thread(root_message, user):
    from .models import ThreadFollow
    ThreadFollow.objects.filter(root_message=root_message, user=user).delete()


def followed_threads(user, company):
    """Fils suivis par `user` (boîte « Fils ») avec compteur de non-lus, triés
    par activité récente. Scopé société ; ne fuite jamais un fil d'une autre
    société (le message racine porte `company`)."""
    from .models import ThreadFollow

    follows = (ThreadFollow.objects
               .filter(user=user, root_message__company=company)
               .select_related('root_message', 'root_message__conversation')
               .order_by('-root_message__created_at'))
    out = []
    for f in follows:
        root = f.root_message
        qs = root.replies.filter(deleted_at__isnull=True)
        if f.last_read_at is not None:
            qs = qs.filter(created_at__gt=f.last_read_at)
        out.append({
            'root_message_id': root.pk,
            'conversation_id': root.conversation_id,
            'root_preview': _preview(root),
            'reply_count': thread_reply_count(root),
            'unread': qs.count(),
        })
    return out


def mark_thread_read(root_message, user, when=None):
    from .models import ThreadFollow
    when = when or timezone.now()
    updated = ThreadFollow.objects.filter(
        root_message=root_message, user=user).update(last_read_at=when)
    return updated > 0


def post_system_message(conversation, body, *, record_type=None, record_id=None):
    """Poste un message SYSTÈME (sender=None) dans une conversation (XKB33).

    Utilisé par le webhook WhatsApp entrant pour surfacer le message reçu dans
    la conversation dédiée sans auteur ERP. Best-effort, jamais bloquant.
    `record_type`/`record_id` permettent d'attacher la carte lead partagée."""
    from .models import Message

    if conversation is None:
        return None
    try:
        shared_ct = None
        shared_label = ''
        if record_type and record_id:
            company = conversation.company
            card = _record_card(record_type, record_id, company)
            if card is not None:
                shared_ct = _content_type_for(record_type)
                subtitle = card.get('subtitle') or ''
                shared_label = (
                    f"{card.get('label', '')} — {subtitle}".strip(' —')
                    if subtitle else card.get('label', ''))
        msg = Message.objects.create(
            company=conversation.company,
            conversation=conversation,
            sender=None,
            body=body or '',
            kind=Message.Kind.SYSTEM,
            shared_content_type=shared_ct,
            shared_object_id=(int(record_id) if (shared_ct and record_id) else None),
            shared_label=shared_label,
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])
        return msg
    except Exception:  # noqa: BLE001 — jamais bloquant pour le webhook
        return None


# ── XKB27 — messages programmés, rappels & signets ────────────────────

def schedule_message(*, conversation, sender, company, body, scheduled_at):
    """« Envoyer plus tard » : crée un `ScheduledMessage` PENDING. Le message
    réel n'est créé qu'au sweep, à `scheduled_at` (jamais avant)."""
    from .models import ScheduledMessage
    if scheduled_at is None or scheduled_at <= timezone.now():
        raise ValueError("L'heure programmée doit être dans le futur.")
    return ScheduledMessage.objects.create(
        company=company, conversation=conversation, sender=sender,
        body=body or '', scheduled_at=scheduled_at)


def cancel_scheduled_message(scheduled, user):
    """Annule un message programmé avant son heure — auteur seulement."""
    from .models import ScheduledMessage
    if scheduled.sender_id != getattr(user, 'pk', None):
        raise PermissionError('Seul l\'auteur peut annuler ce message.')
    if scheduled.status != ScheduledMessage.Status.PENDING:
        raise ValueError('Ce message a déjà été envoyé ou annulé.')
    scheduled.status = ScheduledMessage.Status.CANCELLED
    scheduled.save(update_fields=['status'])
    return scheduled


def sweep_scheduled_messages(now=None):
    """Sweep Celery beat : envoie tout `ScheduledMessage` PENDING dû (à
    `scheduled_at` ou avant), jamais avant l'heure. Best-effort par ligne :
    une panne isolée passe la ligne suivante à `failed` sans interrompre le
    sweep. Retourne le nombre envoyé."""
    from .models import ScheduledMessage
    now = now or timezone.now()
    due = ScheduledMessage.objects.filter(
        status=ScheduledMessage.Status.PENDING, scheduled_at__lte=now)
    sent = 0
    for sched in due:
        try:
            msg = create_message(
                conversation=sched.conversation, sender=sched.sender,
                company=sched.company, body=sched.body)
            sched.status = ScheduledMessage.Status.SENT
            sched.sent_message = msg
            sched.save(update_fields=['status', 'sent_message'])
            sent += 1
        except Exception:  # pragma: no cover - défensif
            sched.status = ScheduledMessage.Status.FAILED
            sched.save(update_fields=['status'])
    return sent


def remind_me(message, user, remind_at):
    """« Me rappeler ce message » : re-surface le message dans l'inbox
    notifications de l'utilisateur à l'heure choisie."""
    from .models import MessageReminder
    if remind_at is None or remind_at <= timezone.now():
        raise ValueError("L'heure de rappel doit être dans le futur.")
    return MessageReminder.objects.create(
        message=message, user=user, remind_at=remind_at)


def cancel_reminder(reminder, user):
    from .models import MessageReminder
    if reminder.user_id != getattr(user, 'pk', None):
        raise PermissionError('Seul le créateur peut annuler ce rappel.')
    if reminder.status != MessageReminder.Status.PENDING:
        raise ValueError('Ce rappel a déjà été envoyé ou annulé.')
    reminder.status = MessageReminder.Status.CANCELLED
    reminder.save(update_fields=['status'])
    return reminder


def sweep_reminders(now=None):
    """Sweep Celery beat : notifie chaque rappel PENDING dû, via le point
    d'entrée `notify()` (in-app + Web Push), best-effort par ligne."""
    from .models import MessageReminder
    now = now or timezone.now()
    due = (MessageReminder.objects
           .filter(status=MessageReminder.Status.PENDING, remind_at__lte=now)
           .select_related('message', 'user', 'message__conversation'))
    sent = 0
    for rem in due:
        try:
            _notify_reminder(rem)
            rem.status = MessageReminder.Status.SENT
            rem.save(update_fields=['status'])
            sent += 1
        except Exception:  # pragma: no cover - défensif
            continue
    return sent


def _notify_reminder(reminder):
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
    except Exception:  # pragma: no cover - défensif
        return
    msg = reminder.message
    link = f'/messages/{msg.conversation_id}'
    notify(reminder.user, EventType.CHAT_MESSAGE,
           'Rappel : message enregistré', body=_preview(msg), link=link,
           company=msg.company)


def toggle_bookmark(message, user):
    """Bascule un signet personnel sur `message` pour `user`."""
    from .models import MessageBookmark
    existing = MessageBookmark.objects.filter(
        message=message, user=user).first()
    if existing is not None:
        existing.delete()
        return 'removed'
    MessageBookmark.objects.create(message=message, user=user)
    return 'added'


def list_bookmarks(user, company):
    """Messages enregistrés par `user`, scopés société, plus récents d'abord."""
    from .models import MessageBookmark
    return list(
        MessageBookmark.objects
        .filter(user=user, message__company=company)
        .select_related('message', 'message__conversation')
        .order_by('-created_at', '-id'))


# ── XKB28 — réponses enregistrées (snippets) ──────────────────────────

def visible_canned_responses(user, company, prefix=None):
    """Snippets visibles par `user` : les siens (personnels) + ceux de la
    société — jamais les personnels d'un autre utilisateur, jamais
    cross-tenant. `prefix` filtre par début de raccourci (autocomplétion)."""
    from django.db.models import Q

    from .models import CannedResponse
    qs = CannedResponse.objects.filter(company=company).filter(
        Q(scope=CannedResponse.Scope.COMPANY)
        | Q(scope=CannedResponse.Scope.PERSONAL, owner=user))
    if prefix:
        qs = qs.filter(shortcut__istartswith=prefix)
    return list(qs.order_by('shortcut'))


def create_canned_response(user, company, *, shortcut, body, scope):
    """Crée un snippet. `scope=company` le partage à toute la société
    (owner=None) ; `scope=personal` reste privé au créateur."""
    from django.db import IntegrityError

    from .models import CannedResponse
    shortcut = (shortcut or '').strip().lstrip(':')
    if not shortcut:
        raise ValueError('Raccourci requis.')
    if scope not in dict(CannedResponse.Scope.choices):
        raise ValueError('Portée invalide.')
    owner = None if scope == CannedResponse.Scope.COMPANY else user
    try:
        return CannedResponse.objects.create(
            company=company, owner=owner, shortcut=shortcut,
            body=body or '', scope=scope)
    except IntegrityError:
        raise ValueError('Ce raccourci existe déjà dans cette portée.')


# ── XKB30 — sondages dans les canaux ───────────────────────────────────

@transaction.atomic
def create_poll(*, conversation, sender, company, question, options,
                allow_multiple=False, is_anonymous=False):
    """Crée un message `kind=poll` + son `Poll`/`PollOption`s. Le message est
    créé via `create_message` (scoping/permissions déjà vérifiés en amont par
    la vue) — pas de notification de mentions ici (sujet différent : le fan-out
    S9 générique s'applique quand même, best-effort)."""
    from .models import Message, Poll, PollOption

    cleaned = [o.strip() for o in (options or []) if (o or '').strip()]
    if len(cleaned) < 2:
        raise ValueError('Un sondage nécessite au moins 2 options.')
    if not (question or '').strip():
        raise ValueError('La question du sondage est requise.')

    msg = create_message(
        conversation=conversation, sender=sender, company=company,
        body=question, kind=Message.Kind.POLL)
    poll = Poll.objects.create(
        message=msg, question=question.strip(),
        allow_multiple=bool(allow_multiple), is_anonymous=bool(is_anonymous))
    for i, label in enumerate(cleaned):
        PollOption.objects.create(poll=poll, label=label, order=i)
    return poll


@transaction.atomic
def vote_poll(poll, user, option_ids):
    """Enregistre le(s) vote(s) de `user`. Choix unique : retire les votes
    précédents de l'utilisateur sur ce sondage avant d'enregistrer le(s)
    nouveau(x). Un sondage clôturé refuse tout nouveau vote."""
    from .models import PollOption, PollVote

    if poll.closed_at is not None:
        raise ValueError('Ce sondage est clôturé.')
    wanted = {int(i) for i in (option_ids or []) if str(i).isdigit()}
    valid_options = list(
        PollOption.objects.filter(poll=poll, pk__in=wanted))
    if not valid_options:
        raise ValueError('Option de vote invalide.')
    if not poll.allow_multiple and len(valid_options) > 1:
        raise ValueError('Ce sondage n\'autorise qu\'un seul choix.')

    # Retire les votes précédents de l'utilisateur sur CE sondage (choix
    # unique ou remplacement complet en choix multiple — comportement simple
    # et prévisible : voter = redéfinir son/ses choix).
    PollVote.objects.filter(
        option__poll=poll, user=user).delete()
    for opt in valid_options:
        PollVote.objects.create(option=opt, user=user)
    return valid_options


def close_poll(poll, user):
    """Clôture un sondage — l'auteur du message racine uniquement."""
    if poll.message.sender_id != getattr(user, 'pk', None):
        raise PermissionError('Seul l\'auteur peut clôturer ce sondage.')
    if poll.closed_at is None:
        poll.closed_at = timezone.now()
        poll.save(update_fields=['closed_at'])
    return poll


def poll_results(poll, requesting_user=None):
    """Résultats agrégés : compte par option + total votants. Si le sondage
    est anonyme, la liste des votants EST MASQUÉE (jamais retournée), même
    au créateur."""
    options = list(poll.options.all().order_by('order', 'id'))
    out = {
        'poll_id': poll.pk,
        'question': poll.question,
        'allow_multiple': poll.allow_multiple,
        'is_anonymous': poll.is_anonymous,
        'closed_at': poll.closed_at,
        'options': [],
        'my_vote_option_ids': [],
    }
    for opt in options:
        votes = list(opt.votes.select_related('user'))
        entry = {
            'id': opt.pk,
            'label': opt.label,
            'vote_count': len(votes),
        }
        if not poll.is_anonymous:
            entry['voter_ids'] = [v.user_id for v in votes
                                  if v.user_id is not None]
        if requesting_user is not None and any(
                v.user_id == requesting_user.pk for v in votes):
            out['my_vote_option_ids'].append(opt.pk)
        out['options'].append(entry)
    return out


# ── XKB32 — rétention & export des conversations (loi 09-08) ──────────

def get_retention_policy(company, conversation_kind):
    """Politique active pour ce type de conversation, ou None (= aucune
    purge, comportement inchangé) — DÉFAUT du modèle."""
    from .models import RetentionPolicy
    return RetentionPolicy.objects.filter(
        company=company, conversation_kind=conversation_kind).first()


def set_retention_policy(company, conversation_kind, retention_months, user):
    """Pose (ou lève, si `retention_months=None`) la politique de rétention
    pour un type de conversation. Admin-only côté vue."""
    from .models import RetentionPolicy
    policy, _ = RetentionPolicy.objects.get_or_create(
        company=company, conversation_kind=conversation_kind)
    policy.retention_months = retention_months
    policy.updated_by = user
    policy.save(update_fields=['retention_months', 'updated_by', 'updated_at'])
    return policy


def _months_ago(now, months):
    """Soustrait `months` mois à `now`, SANS dépendance externe (pas de
    `dateutil`, comme le reste du projet — voir `apps/contrats/models.py`).
    Le jour est borné au dernier jour du mois cible (ex. 31 janvier - 1 mois
    -> 31 décembre reste valide ; 31 mars - 1 mois -> 28/29 février)."""
    import calendar
    total_month_index = now.month - 1 - months
    year = now.year + total_month_index // 12
    month = total_month_index % 12 + 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


def sweep_retention(company, now=None):
    """Sweep de rétention pour UNE société : pour chaque type de conversation
    ayant une politique active (`retention_months` non nul), soft-delete
    (`deleted_at`) les messages plus vieux que la fenêtre. SANS politique,
    RIEN n'est purgé (comportement par défaut inchangé). Journalise
    TOUJOURS l'exécution, même à 0 purge (traçabilité CNDP)."""
    from .models import Message, RetentionPolicy, RetentionSweepRun

    now = now or timezone.now()
    total = 0
    details = []
    policies = RetentionPolicy.objects.filter(
        company=company, retention_months__isnull=False)
    for policy in policies:
        cutoff = _months_ago(now, policy.retention_months)
        qs = Message.objects.filter(
            company=company,
            conversation__kind=policy.conversation_kind,
            deleted_at__isnull=True,
            created_at__lt=cutoff)
        count = qs.count()
        if count:
            qs.update(deleted_at=now)
        total += count
        details.append(
            f'{policy.conversation_kind}: {count} message(s) purgé(s) '
            f'(> {policy.retention_months} mois)')

    RetentionSweepRun.objects.create(
        company=company, messages_purged=total,
        detail='; '.join(details) or 'Aucune politique active.')
    return total


def export_conversation(conversation, fmt='json'):
    """Export intégral (JSON/CSV + PJ) d'une conversation pour audit/conformité
    CNDP — scopé société de l'appelant (vérifié en amont par la vue). Renvoie
    un dict JSON-sérialisable (le format CSV est produit côté vue à partir de
    la même structure, pour rester une seule source de vérité)."""
    messages = list(
        conversation.messages.all()
        .select_related('sender')
        .prefetch_related('attachments')
        .order_by('created_at', 'id'))
    rows = []
    for m in messages:
        rows.append({
            'id': m.id,
            'sender': (getattr(m.sender, 'username', '') if m.sender_id
                       else 'système'),
            'body': m.body,
            'kind': m.kind,
            'created_at': m.created_at.isoformat() if m.created_at else '',
            'deleted': m.deleted_at is not None,
            'attachments': [
                {'filename': a.filename, 'file_key': a.file_key,
                 'mime': a.mime}
                for a in m.attachments.all()
            ],
        })
    return {
        'conversation_id': conversation.pk,
        'conversation_name': conversation.name or f'Conversation {conversation.pk}',
        'kind': conversation.kind,
        'messages': rows,
    }


# ── ZCTR12 — canal comme liste de diffusion e-mail ─────────────────────

def set_channel_alias(conversation, alias_email, user):
    """Pose (ou lève, si vide) l'alias e-mail d'un canal. Unique par société
    (contrainte DB `chat_conv_alias_email_uniq`) — une violation remonte en
    `ValueError` lisible côté vue plutôt qu'une `IntegrityError` brute."""
    from django.db import IntegrityError

    alias = (alias_email or '').strip().lower() or None
    conversation.alias_email = alias
    try:
        conversation.save(update_fields=['alias_email'])
    except IntegrityError:
        raise ValueError(
            'Cet alias e-mail est déjà utilisé par un autre canal de la '
            'société.')
    return conversation


def _email_gated():
    """Vrai si l'email sortant est réellement configuré (SENDGRID/SMTP).
    Sans configuration : NO-OP complet, comportement du canal interne
    inchangé — jamais d'exception."""
    try:
        from apps.ventes.email_service import is_email_configured
        return bool(is_email_configured())
    except Exception:  # pragma: no cover - défensif
        return False


def notify_channel_alias_email(message):
    """(a) — Un message posté dans un canal ALIASÉ est aussi envoyé par
    e-mail aux membres ayant opté (préférence `notifications` existante,
    canal email de `CHAT_MESSAGE`). NO-OP complet si l'email n'est pas
    configuré OU si la conversation n'a pas d'alias — jamais bloquant,
    jamais d'exception vers l'appelant."""
    conv = message.conversation
    if not conv.alias_email or not _email_gated():
        return 0
    try:
        from apps.notifications.services import _dispatch_email, resolve_prefs
        from apps.notifications.models import EventType
    except Exception:  # pragma: no cover - défensif
        return 0

    from .models import ConversationMember

    sent = 0
    title = f'[{conv.name or conv.alias_email}] Nouveau message'
    body = _preview(message)
    members = (ConversationMember.objects
               .filter(conversation=conv)
               .exclude(is_muted=True)
               .select_related('user'))
    for m in members:
        u = m.user
        if u is None or (message.sender_id and u.pk == message.sender_id):
            continue
        try:
            prefs = resolve_prefs(u, EventType.CHAT_MESSAGE)
            if not prefs.get('email'):
                continue  # opt-in requis — jamais un envoi non consenti.
            if _dispatch_email(u, title, body):
                sent += 1
        except Exception:  # pragma: no cover - défensif
            continue
    return sent


def receive_channel_alias_email(company, *, to_alias, from_email, subject='',
                                body=''):
    """(b) — E-mail entrant vers un alias (webhook inbound GATED, complet
    NO-OP sans configuration) : crée un `Message` dans le canal attribué à
    l'expéditeur SI reconnu (via l'adresse e-mail d'un utilisateur de la
    société), sinon en SYSTÈME (jamais un message anonyme attribué à
    quelqu'un d'autre). Toujours scopé société ; alias introuvable -> None."""
    from django.contrib.auth import get_user_model

    from .models import Conversation

    alias = (to_alias or '').strip().lower()
    if not alias:
        return None
    conv = Conversation.objects.filter(
        company=company, alias_email=alias,
        kind=Conversation.Kind.CHANNEL).first()
    if conv is None:
        return None

    text = (body or subject or '').strip()
    User = get_user_model()
    sender_email = (from_email or '').strip().lower()
    sender = (User.objects.filter(
        company=company, email__iexact=sender_email).first()
        if sender_email else None)

    if sender is not None and _is_conversation_member(sender, conv):
        return create_message(
            conversation=conv, sender=sender, company=company, body=text)
    label = f'E-mail entrant de {sender_email or "expéditeur inconnu"}'
    return post_system_message(conv, f'{label} : {text}'[:2000])


def _is_conversation_member(user, conversation):
    """Mini-doublure locale de `permissions.is_member` (évite un import
    circulaire `services.py` <-> `permissions.py`) pour
    `receive_channel_alias_email`."""
    if user is None or not getattr(user, 'pk', None):
        return False
    if getattr(conversation, 'company_id', None) != getattr(
            user, 'company_id', None):
        return False
    return conversation.members.filter(user=user).exists()


def delete_canned_response(canned, user):
    """Supprime un snippet, scopé société. Un personnel n'est supprimable que
    par son propriétaire ; un snippet société (portée collective, pas de
    propriétaire unique) est supprimable par tout membre de la société."""
    from .models import CannedResponse
    if canned.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Hors de votre société.")
    if (canned.scope == CannedResponse.Scope.PERSONAL
            and canned.owner_id != getattr(user, 'pk', None)):
        raise PermissionError('Seul le créateur peut supprimer ce snippet.')
    canned.delete()
