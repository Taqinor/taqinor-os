"""Points d'accroche par signaux de la messagerie interne.

S9 — notifications de nouveau message : émises explicitement par
`services.create_message` (via `transaction.on_commit`) plutôt que par un signal
`post_save`, afin de connaître les @mentions résolues et la sourdine par membre.

S11 — transcription des mémos vocaux : un `post_save` sur `MessageAttachment`
enfile la tâche Celery de transcription dès qu'une pièce VOCALE est créée en
attente (`transcript_status=pending`). L'enfilement passe par
`services.enqueue_voice_transcription` (sur `transaction.on_commit`) pour ne se
déclencher qu'une fois la pièce réellement persistée.

Ce module est importé par `apps.py.ready()`.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MessageAttachment
from . import services


@receiver(post_save, sender=MessageAttachment,
          dispatch_uid='chat_voice_transcription')
def _enqueue_voice_transcription(sender, instance, created, **kwargs):
    """S11 — à la création d'un mémo vocal en attente, enfile la transcription.

    On ne réagit qu'à la CRÉATION d'une pièce VOCALE encore `pending` ; les
    pièces non vocales, déjà transcrites, en échec ou `disabled` (transcription
    coupée) sont ignorées — le mémo reste lisible dans tous les cas.
    """
    if not created:
        return
    if instance.kind != MessageAttachment.Kind.VOICE:
        return
    if (instance.transcript_status
            != MessageAttachment.TranscriptStatus.PENDING):
        return
    services.enqueue_voice_transcription(instance.pk)
