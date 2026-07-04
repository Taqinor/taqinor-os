"""S11 — pipeline Celery de transcription des mémos vocaux du chat.

À l'upload d'un mémo vocal (S6 : `MessageAttachment.kind=voice`,
`transcript_status=pending`), un signal enfile `task_transcribe_voice_attachment`
(voir `signals.py`). La tâche :

  1. récupère l'audio depuis MinIO (`records.storage.fetch_attachment`),
  2. appelle l'endpoint self-hosted FastAPI `/chat/transcribe` (S10),
  3. écrit `transcript`/`transcript_lang`/`transcript_status=done` (ou `failed`).

Sûreté :
  * idempotente — ne (re)transcrit que les pièces encore `pending` ;
  * résiliente — après les retries Celery, toute panne termine en
    `transcript_status=failed`, JAMAIS une exception qui casserait l'upload ;
  * NO-OP gracieux — si la transcription est désactivée
    (`CHAT_TRANSCRIPTION_ENABLED` faux, pas de service, ou réponse
    `enabled=False` de FastAPI), la pièce passe à `disabled` et le mémo reste
    lisible.

Multi-tenant : la pièce porte la société via son message/conversation ; on relaie
un JWT d'accès frappé pour l'expéditeur du message (même `SECRET_KEY`/HS256 que
SIMPLE_JWT), donc FastAPI réapplique l'auth côté service.
"""
import logging

import httpx
from celery import shared_task

logger = logging.getLogger(__name__)

# Délai max d'un appel de transcription (s) — un mémo court est rapide ; on borne
# pour ne pas bloquer un worker indéfiniment si le service rame.
_TRANSCRIBE_TIMEOUT = 120


def _transcription_enabled():
    """Vrai si la transcription self-hosted est activée côté Django."""
    from django.conf import settings
    return bool(getattr(settings, 'CHAT_TRANSCRIPTION_ENABLED', False))


def _fastapi_transcribe_url():
    """URL interne de l'endpoint FastAPI `/transcribe` (S10).

    Base configurable via `FASTAPI_INTERNAL_URL` (settings ou env) ; défaut sur
    le nom de service docker-compose `fastapi_ia:8001` avec le `root_path`
    `/api/fastapi` puis le préfixe `/chat` du routeur de transcription.
    """
    import os

    from django.conf import settings
    base = (getattr(settings, 'FASTAPI_INTERNAL_URL', '')
            or os.environ.get('FASTAPI_INTERNAL_URL', '')
            or 'http://fastapi_ia:8001/api/fastapi')
    return base.rstrip('/') + '/chat/transcribe'


def _service_token_for(user):
    """Jeton d'accès JWT court pour relayer l'auth vers FastAPI.

    Frappé pour l'expéditeur du message via SIMPLE_JWT (même `SECRET_KEY` +
    HS256 que `verify_token` côté FastAPI), il porte `exp` + `token_type=access`,
    exactement ce qu'exige le service. Sans utilisateur exploitable, renvoie ''.
    """
    if user is None:
        return ''
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        return str(AccessToken.for_user(user))
    except Exception:  # pragma: no cover - défensif
        return ''


def _set_status(attachment_id, status, **extra):
    """Écrit l'état (et champs associés) sur la pièce, sans déclencher de signal
    (update direct), best-effort."""
    from .models import MessageAttachment
    MessageAttachment.objects.filter(pk=attachment_id).update(
        transcript_status=status, **extra)


@shared_task(
    bind=True,
    name='chat.transcribe_voice_attachment',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def task_transcribe_voice_attachment(self, attachment_id):
    """Transcrit un mémo vocal et écrit le résultat sur le `MessageAttachment`.

    Idempotente : ne traite que les pièces vocales encore `pending`. Une panne
    transitoire (MinIO, réseau, service) déclenche un retry Celery ; les retries
    épuisés → `transcript_status=failed` sans casser l'upload. Transcription
    désactivée → `disabled`.
    """
    from .models import MessageAttachment

    att = (MessageAttachment.objects
           .select_related('message', 'message__sender')
           .filter(pk=attachment_id).first())
    if att is None:
        logger.info('transcribe: pièce jointe %s introuvable', attachment_id)
        return 'missing'

    # Idempotence : seules les pièces VOCALES encore en attente sont traitées.
    if att.kind != MessageAttachment.Kind.VOICE:
        return 'skip:not-voice'
    if att.transcript_status != MessageAttachment.TranscriptStatus.PENDING:
        return f'skip:{att.transcript_status or "empty"}'

    # NO-OP gracieux si la transcription est désactivée — le mémo reste lisible.
    if not _transcription_enabled():
        _set_status(att.pk, MessageAttachment.TranscriptStatus.DISABLED)
        return 'disabled'

    try:
        # 1) Récupère l'audio depuis MinIO.
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(att.file_key)
        if err or not data:
            raise RuntimeError(err or 'audio vide')

        # 2) Appelle le service FastAPI self-hosted.
        result = _call_transcribe(
            data,
            filename=att.filename or 'memo.webm',
            mime=att.mime or 'audio/webm',
            sender=getattr(att.message, 'sender', None),
        )
    except Exception as exc:  # MinIO / réseau / service / timeout
        return _retry_or_fail(self, att.pk, exc)

    # FastAPI signale la transcription désactivée → `disabled` (mémo intact).
    if not result.get('enabled', True):
        _set_status(att.pk, MessageAttachment.TranscriptStatus.DISABLED)
        return 'disabled'

    # 3) Écrit le résultat. Une transcription vide reste un succès (silence).
    text = (result.get('text') or '').strip()
    lang = (result.get('language') or '')[:16]
    _set_status(
        att.pk, MessageAttachment.TranscriptStatus.DONE,
        transcript=text, transcript_lang=lang)
    logger.info('transcribe OK att=%s lang=%s len=%s', att.pk, lang, len(text))
    return 'done'


def _call_transcribe(data, *, filename, mime, sender):
    """POST multipart vers FastAPI `/chat/transcribe`, renvoie son JSON.

    Utilise `httpx` (déjà une dépendance). Lève en cas d'erreur réseau/HTTP pour
    laisser la tâche gérer retry/échec.
    """
    headers = {}
    token = _service_token_for(sender)
    if token:
        headers['Authorization'] = f'Bearer {token}'
    files = {'file': (filename, data, mime)}
    resp = httpx.post(
        _fastapi_transcribe_url(),
        files=files, headers=headers, timeout=_TRANSCRIBE_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _retry_or_fail(task, attachment_id, exc):
    """Relance la tâche tant qu'il reste des retries, sinon marque `failed`.

    On ne propage jamais l'exception au-delà des retries : l'upload du mémo ne
    doit jamais être cassé. On décide AVANT d'appeler `retry` (fiable en mode
    worker comme en mode eager `.apply()`) : si le quota de retries est épuisé,
    on écrit l'état `failed` et on s'arrête ; sinon on relance avec backoff
    exponentiel (`self.retry` lève `Retry`, l'interruption normale d'un retry).
    """
    from .models import MessageAttachment

    retries = task.request.retries or 0
    max_retries = task.max_retries or 0
    logger.warning('transcribe: échec (att=%s, retry=%s/%s): %s',
                   attachment_id, retries, max_retries, exc)
    if retries >= max_retries:
        _set_status(
            attachment_id, MessageAttachment.TranscriptStatus.FAILED)
        logger.error('transcribe: échec définitif att=%s: %s',
                     attachment_id, exc)
        return 'failed'
    raise task.retry(exc=exc, countdown=2 ** retries * 30)


# ── XKB27 — messages programmés & rappels (sweep Celery beat) ─────────

@shared_task(name='chat.send_scheduled_messages')
def task_send_scheduled_messages():
    """Envoie tout `ScheduledMessage` PENDING dû — jamais avant l'heure."""
    from .services import sweep_scheduled_messages
    sent = sweep_scheduled_messages()
    logger.info('chat.send_scheduled_messages: %s message(s) envoyé(s)', sent)
    return sent


@shared_task(name='chat.send_due_reminders')
def task_send_due_reminders():
    """Notifie chaque `MessageReminder` PENDING dû."""
    from .services import sweep_reminders
    sent = sweep_reminders()
    logger.info('chat.send_due_reminders: %s rappel(s) envoyé(s)', sent)
    return sent
