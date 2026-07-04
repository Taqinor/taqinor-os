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
                   mention_ids=None):
    """Crée un message dans une conversation (membre déjà vérifié en amont).

    Gère le partage d'enregistrement (S8) et les @mentions (S9). La société est
    TOUJOURS celle de la conversation/appelant. Lève ValueError si un
    enregistrement partagé n'appartient pas à la société.

    Les @mentions sont résolues depuis le corps (@username/@email) ET, en plus,
    depuis la liste d'ids `mention_ids` fournie par le client (S16) — toujours
    filtrée à l'appartenance, jamais cross-conversation."""
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

    # Notifications (in-app + Web Push), best-effort, après commit.
    transaction.on_commit(lambda: _notify_new_message(msg, mentioned))
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
        body=body, reply_to=root_message, **kwargs)

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
