"""Orchestration de la messagerie interne (écritures + logique transverse).

Tout passe par la société de l'appelant, jamais par le corps de requête. Les
lectures cross-app (cartes lead/devis/chantier) passent par les `selectors.py`
des apps cibles — jamais par leurs modèles/vues (contrat d'import CI).
"""
import re

from django.db import transaction
from django.db.models import Count, Q
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


@transaction.atomic
def create_message(*, conversation, sender, company, body='', kind=None,
                   reply_to=None, record_type=None, record_id=None):
    """Crée un message dans une conversation (membre déjà vérifié en amont).

    Gère le partage d'enregistrement (S8) et les @mentions (S9). La société est
    TOUJOURS celle de la conversation/appelant. Lève ValueError si un
    enregistrement partagé n'appartient pas à la société."""
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

    # @mentions → lignes dédiées (push plus fort).
    mentioned = _resolve_mentions(conversation, body)
    for u in mentioned:
        MessageMention.objects.get_or_create(message=msg, mentioned_user=u)

    # Notifications (in-app + Web Push), best-effort, après commit.
    transaction.on_commit(lambda: _notify_new_message(msg, mentioned))
    return msg


def _notify_new_message(message, mentioned_users):
    """S9 — notifie les autres membres non en sourdine ; @mention = plus fort.

    Réutilise le point d'entrée `notify()` (in-app + Web Push). Respecte les
    préférences utilisateur et la sourdine PAR CONVERSATION."""
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
               .select_related('user'))
    for m in members:
        u = m.user
        if u is None or (sender is not None and u.pk == sender.pk):
            continue
        if u.pk in mentioned_ids:
            event = EventType.CHAT_MENTION
            ntitle = f'{title} vous a mentionné'
        else:
            event = EventType.CHAT_MESSAGE
            ntitle = title
        try:
            notify(u, event, ntitle, body=preview, link=link, company=company)
        except Exception:  # pragma: no cover - défensif
            continue


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
