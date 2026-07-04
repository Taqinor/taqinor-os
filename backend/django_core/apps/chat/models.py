"""Group S — Messagerie interne d'équipe (« Discuss »).

Chat INTERNE entre membres d'une même société : conversations 1-à-1 (DM) et
canaux nommés, avec pièces jointes (image/fichier/voix), @mentions, réactions,
messages épinglés, partage d'un enregistrement ERP (lead/devis/chantier) et
recherche.

Règles fondatrices appliquées ici :
  - MULTI-TENANT STRICT : chaque modèle porte `company` (FK
    authentication.Company), forcée côté serveur, jamais depuis le corps de
    requête. Un viewset est scopé société ET contrôlé par appartenance.
  - ADDITIF / NULLABLE : tout est nouveau ; les colonnes optionnelles sont
    nullables.
  - Texte utilisateur en FRANÇAIS ; clés/énumérations en anglais.

Le transport temps réel reste du POLLING en v1 (choix fondateur 2026-06-21) —
aucune infra WebSocket/Channels ici.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Conversation(models.Model):
    """Une conversation : soit un DM (1-à-1), soit un canal nommé.

    Toujours scopée à UNE société. Les membres sont gérés via
    `ConversationMember` (canal sur invitation : le créateur ajoute les
    membres)."""

    class Kind(models.TextChoices):
        DM = 'dm', 'Message direct'
        CHANNEL = 'channel', 'Canal'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='chat_conversations')
    kind = models.CharField(
        max_length=10, choices=Kind.choices, default=Kind.CHANNEL)
    # Nom du canal (les DM en sont dépourvus : on affiche l'autre membre).
    name = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chat_conversations_created')
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['company', 'kind']),
            models.Index(fields=['company', 'is_archived']),
        ]

    def __str__(self):
        if self.kind == self.Kind.CHANNEL and self.name:
            return f'#{self.name}'
        return f'Conversation {self.pk}'


class ConversationMember(models.Model):
    """Appartenance d'un utilisateur à une conversation.

    Pilote la lecture/écriture (un non-membre est 403), les compteurs de
    non-lus (`last_read_at`) et la sourdine par conversation (`is_muted`)."""

    class Role(models.TextChoices):
        MEMBER = 'member', 'Membre'
        ADMIN = 'admin', 'Administrateur'

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='chat_memberships')
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.MEMBER)
    # Dernière lecture : les messages créés après cette date sont « non lus ».
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class NotificationLevel(models.TextChoices):
        ALL = 'all', 'Tout'
        MENTIONS = 'mentions', 'Mentions seulement'
        MUTED = 'muted', 'Muet'

    # XKB25 — remplace `is_muted` par un niveau à 3 valeurs (additif ;
    # `is_muted` reste et reste synchronisé pour compat ascendante). Défaut
    # `all` préserve le comportement existant (non muet = tout notifié).
    notification_level = models.CharField(
        max_length=10, choices=NotificationLevel.choices,
        default=NotificationLevel.ALL)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Membre de conversation'
        verbose_name_plural = 'Membres de conversation'
        ordering = ['conversation_id', 'id']
        unique_together = [('conversation', 'user')]
        indexes = [
            models.Index(fields=['user', 'conversation']),
        ]

    def __str__(self):
        return f'{self.user_id} ∈ {self.conversation_id}'


class Message(models.Model):
    """Un message dans une conversation.

    `body` contient le texte (vide pour un message voix/record). Soft-delete via
    `deleted_at` (on ne supprime jamais physiquement : on garde le fil). Lien
    générique vers un enregistrement ERP partagé (S8) + libellé figé."""

    class Kind(models.TextChoices):
        TEXT = 'text', 'Texte'
        VOICE = 'voice', 'Mémo vocal'
        SYSTEM = 'system', 'Système'
        RECORD = 'record', 'Enregistrement partagé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='chat_messages')
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chat_messages')
    body = models.TextField(blank=True, default='')
    kind = models.CharField(
        max_length=10, choices=Kind.choices, default=Kind.TEXT)
    reply_to = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    pinned_at = models.DateTimeField(null=True, blank=True)
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chat_messages_pinned')

    # ── S8 — partage d'un enregistrement ERP (lien générique + snapshot). ──
    shared_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+')
    shared_object_id = models.PositiveIntegerField(null=True, blank=True)
    shared_object = GenericForeignKey('shared_content_type', 'shared_object_id')
    # Libellé figé au moment du partage (rendu même si la cible change/disparaît).
    shared_label = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f'Message {self.pk} ({self.conversation_id})'


class MessageAttachment(models.Model):
    """Pièce jointe d'un message — stockée via `apps.records.storage` (MinIO).

    Miroir des champs de `records.storage.store_attachment`
    (`file_key`/`filename`/`mime`/`size`). Les mémos vocaux portent en plus la
    durée et l'état de transcription (self-hosted faster-whisper, S10/S11)."""

    class Kind(models.TextChoices):
        IMAGE = 'image', 'Image'
        FILE = 'file', 'Fichier'
        VOICE = 'voice', 'Mémo vocal'

    class TranscriptStatus(models.TextChoices):
        PENDING = 'pending', 'En attente'
        DONE = 'done', 'Transcrit'
        FAILED = 'failed', 'Échec'
        DISABLED = 'disabled', 'Désactivé'

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='attachments')
    file_key = models.CharField(max_length=512)
    filename = models.CharField(max_length=255, blank=True, default='')
    mime = models.CharField(max_length=120, blank=True, default='')
    size = models.PositiveIntegerField(default=0)
    kind = models.CharField(
        max_length=10, choices=Kind.choices, default=Kind.FILE)

    # ── Mémo vocal ──
    duration_s = models.PositiveIntegerField(null=True, blank=True)
    transcript = models.TextField(blank=True, default='')
    transcript_lang = models.CharField(max_length=16, blank=True, default='')
    transcript_status = models.CharField(
        max_length=10, choices=TranscriptStatus.choices,
        blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pièce jointe de message'
        verbose_name_plural = 'Pièces jointes de message'
        ordering = ['id']
        indexes = [
            models.Index(fields=['message', 'kind']),
        ]

    def __str__(self):
        return f'{self.kind}:{self.filename or self.file_key}'


class MessageReaction(models.Model):
    """Réaction emoji d'un utilisateur sur un message (unique par emoji)."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='chat_reactions')
    emoji = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Réaction'
        verbose_name_plural = 'Réactions'
        ordering = ['id']
        unique_together = [('message', 'user', 'emoji')]
        indexes = [
            models.Index(fields=['message']),
        ]

    def __str__(self):
        return f'{self.user_id} {self.emoji} → {self.message_id}'


class MessageMention(models.Model):
    """@mention ciblée dans un message — déclenche un push « CHAT_MENTION »."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='mentions')
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='chat_mentions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mention'
        verbose_name_plural = 'Mentions'
        ordering = ['id']
        unique_together = [('message', 'mentioned_user')]
        indexes = [
            models.Index(fields=['mentioned_user', 'message']),
        ]

    def __str__(self):
        return f'@{self.mentioned_user_id} dans {self.message_id}'


class ThreadFollow(models.Model):
    """XKB24 — suivi d'un fil (le message racine porte le fil).

    Le premier posteur (auteur du message racine) et tout répondant sont
    auto-suivis (`get_or_create` dans `services.reply_in_thread`). Un
    utilisateur peut aussi suivre/ne plus suivre manuellement. Utilisé pour la
    boîte « Fils » (fils suivis + non-lus) et pour notifier UNIQUEMENT les
    suiveurs (jamais tout le canal)."""

    root_message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='thread_followers')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='chat_thread_follows')
    # Dernière lecture du fil par ce suiveur (badge non-lus de la boîte Fils).
    last_read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Suivi de fil'
        verbose_name_plural = 'Suivis de fil'
        ordering = ['id']
        unique_together = [('root_message', 'user')]
        indexes = [
            models.Index(fields=['user', 'root_message']),
        ]

    def __str__(self):
        return f'{self.user_id} suit fil {self.root_message_id}'
