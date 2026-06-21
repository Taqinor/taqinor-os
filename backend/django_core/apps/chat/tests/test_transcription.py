"""S11 — pipeline Django de transcription des mémos vocaux.

Couvre, avec l'appel FastAPI ET la récupération MinIO STUBÉS (aucun service ni
poids réels en CI) :
  (a) succès stubé          → `transcript` stocké + `transcript_status=done` ;
  (b) transcription coupée  → `transcript_status=disabled` + le mémo reste intact
                              (l'upload renvoie 201 et la pièce reste lisible) ;
  (c) échec (MinIO/réseau)  → `transcript_status=failed` après les retries ;
  (d) idempotence           → une pièce déjà transcrite n'est pas retraitée.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from authentication.models import Company
from django.contrib.auth import get_user_model

from apps.chat.models import (
    Conversation, ConversationMember, Message, MessageAttachment,
)
from apps.chat import tasks

User = get_user_model()


def _company():
    c, _ = Company.objects.get_or_create(
        slug='trans-co', defaults={'nom': 'Trans Co'})
    return c


def _user(company, username='vince'):
    return User.objects.create_user(
        username=username, password='x', company=company)


def _voice_attachment(company, sender, status):
    """Crée un message + une pièce VOCALE dans l'état de transcription donné.

    On crée la pièce directement avec le statut voulu pour ne pas déclencher le
    signal d'enfilement réel (on teste la tâche isolément)."""
    conv = Conversation.objects.create(
        company=company, kind=Conversation.Kind.CHANNEL, name='g',
        created_by=sender)
    ConversationMember.objects.create(conversation=conv, user=sender)
    msg = Message.objects.create(
        company=company, conversation=conv, sender=sender,
        kind=Message.Kind.VOICE)
    return MessageAttachment.objects.create(
        message=msg, kind=MessageAttachment.Kind.VOICE,
        file_key='attachments/memo.webm', filename='memo.webm',
        mime='audio/webm', size=1234, transcript_status=status)


class S11TranscriptionTaskTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)

    # (a) Succès stubé → transcript stocké + status done.
    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.httpx.post')
    @patch('apps.records.storage.fetch_attachment')
    def test_success_stores_transcript(self, mock_fetch, mock_post):
        mock_fetch.return_value = (b'\x1a\x45\xdf\xa3audiobytes', None)
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            'text': 'Bonjour, ceci est un mémo.', 'language': 'fr',
            'enabled': True}

        att = _voice_attachment(
            self.company, self.user,
            MessageAttachment.TranscriptStatus.PENDING)

        result = tasks.task_transcribe_voice_attachment.apply(
            args=[att.pk]).get()

        att.refresh_from_db()
        self.assertEqual(result, 'done')
        self.assertEqual(
            att.transcript_status, MessageAttachment.TranscriptStatus.DONE)
        self.assertEqual(att.transcript, 'Bonjour, ceci est un mémo.')
        self.assertEqual(att.transcript_lang, 'fr')
        # L'appel FastAPI a bien reçu un multipart avec le fichier.
        self.assertTrue(mock_post.called)
        _, kwargs = mock_post.call_args
        self.assertIn('files', kwargs)

    # (b) Désactivé → status disabled, le mémo reste intact, sans appel réseau.
    @override_settings(CHAT_TRANSCRIPTION_ENABLED=False)
    @patch('apps.chat.tasks.httpx.post')
    @patch('apps.records.storage.fetch_attachment')
    def test_disabled_is_noop_memo_intact(self, mock_fetch, mock_post):
        att = _voice_attachment(
            self.company, self.user,
            MessageAttachment.TranscriptStatus.PENDING)

        result = tasks.task_transcribe_voice_attachment.apply(
            args=[att.pk]).get()

        att.refresh_from_db()
        self.assertEqual(result, 'disabled')
        self.assertEqual(
            att.transcript_status,
            MessageAttachment.TranscriptStatus.DISABLED)
        # Le mémo reste lisible : file_key préservé, aucun service appelé.
        self.assertEqual(att.file_key, 'attachments/memo.webm')
        self.assertFalse(mock_post.called)
        self.assertFalse(mock_fetch.called)

    # (b bis) FastAPI répond enabled=False → disabled (mémo intact).
    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.httpx.post')
    @patch('apps.records.storage.fetch_attachment')
    def test_service_reports_disabled(self, mock_fetch, mock_post):
        mock_fetch.return_value = (b'\x1a\x45\xdf\xa3audio', None)
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            'enabled': False, 'detail': 'off'}

        att = _voice_attachment(
            self.company, self.user,
            MessageAttachment.TranscriptStatus.PENDING)

        result = tasks.task_transcribe_voice_attachment.apply(
            args=[att.pk]).get()

        att.refresh_from_db()
        self.assertEqual(result, 'disabled')
        self.assertEqual(
            att.transcript_status,
            MessageAttachment.TranscriptStatus.DISABLED)

    # (c) Panne (MinIO introuvable) → failed après épuisement des retries.
    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.httpx.post')
    @patch('apps.records.storage.fetch_attachment')
    def test_failure_sets_failed(self, mock_fetch, mock_post):
        mock_fetch.return_value = (None, 'Fichier introuvable.')

        att = _voice_attachment(
            self.company, self.user,
            MessageAttachment.TranscriptStatus.PENDING)

        # `.apply()` exécute en eager : les retries sont rejoués jusqu'à
        # MaxRetries, puis la pièce passe `failed` sans lever.
        result = tasks.task_transcribe_voice_attachment.apply(
            args=[att.pk]).get()

        att.refresh_from_db()
        self.assertEqual(result, 'failed')
        self.assertEqual(
            att.transcript_status, MessageAttachment.TranscriptStatus.FAILED)
        self.assertFalse(mock_post.called)

    # (c bis) Erreur réseau du service → failed.
    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.httpx.post')
    @patch('apps.records.storage.fetch_attachment')
    def test_network_error_sets_failed(self, mock_fetch, mock_post):
        mock_fetch.return_value = (b'\x1a\x45\xdf\xa3audio', None)
        mock_post.side_effect = RuntimeError('connexion refusée')

        att = _voice_attachment(
            self.company, self.user,
            MessageAttachment.TranscriptStatus.PENDING)

        result = tasks.task_transcribe_voice_attachment.apply(
            args=[att.pk]).get()

        att.refresh_from_db()
        self.assertEqual(result, 'failed')
        self.assertEqual(
            att.transcript_status, MessageAttachment.TranscriptStatus.FAILED)

    # (d) Idempotence : une pièce déjà transcrite n'est pas retraitée.
    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.httpx.post')
    @patch('apps.records.storage.fetch_attachment')
    def test_idempotent_skip_when_not_pending(self, mock_fetch, mock_post):
        att = _voice_attachment(
            self.company, self.user,
            MessageAttachment.TranscriptStatus.DONE)
        att.transcript = 'déjà fait'
        att.save(update_fields=['transcript'])

        result = tasks.task_transcribe_voice_attachment.apply(
            args=[att.pk]).get()

        att.refresh_from_db()
        self.assertTrue(result.startswith('skip'))
        self.assertEqual(att.transcript, 'déjà fait')
        self.assertFalse(mock_post.called)
        self.assertFalse(mock_fetch.called)

    def test_missing_attachment_is_safe(self):
        result = tasks.task_transcribe_voice_attachment.apply(
            args=[999999]).get()
        self.assertEqual(result, 'missing')


class S11SignalEnqueueTests(TestCase):
    """Le signal post_save enfile la tâche après commit pour un mémo pending."""

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company, 'enq')

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.task_transcribe_voice_attachment.delay')
    def test_pending_voice_enqueues_on_commit(self, mock_delay):
        # captureOnCommitCallbacks rejoue les callbacks transaction.on_commit.
        with self.captureOnCommitCallbacks(execute=True):
            att = _voice_attachment(
                self.company, self.user,
                MessageAttachment.TranscriptStatus.PENDING)
        mock_delay.assert_called_once_with(att.pk)

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.task_transcribe_voice_attachment.delay')
    def test_non_voice_does_not_enqueue(self, mock_delay):
        conv = Conversation.objects.create(
            company=self.company, kind=Conversation.Kind.CHANNEL, name='g',
            created_by=self.user)
        msg = Message.objects.create(
            company=self.company, conversation=conv, sender=self.user)
        with self.captureOnCommitCallbacks(execute=True):
            MessageAttachment.objects.create(
                message=msg, kind=MessageAttachment.Kind.IMAGE,
                file_key='attachments/p.png', mime='image/png', size=1)
        mock_delay.assert_not_called()

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    @patch('apps.chat.tasks.task_transcribe_voice_attachment.delay')
    def test_disabled_voice_does_not_enqueue(self, mock_delay):
        # Une pièce vocale créée déjà `disabled` (transcription coupée à
        # l'upload) ne doit pas être enfilée.
        with self.captureOnCommitCallbacks(execute=True):
            _voice_attachment(
                self.company, self.user,
                MessageAttachment.TranscriptStatus.DISABLED)
        mock_delay.assert_not_called()
