"""NTMOB30 — transcription vocale synchrone et générique (notes de terrain)."""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

URL = '/api/django/chat/transcrire/'


def audio(nom='note.webm'):
    return SimpleUploadedFile(nom, b'\x00\x01audio', content_type='audio/webm')


class Ntmob30TranscrireTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTMOB30',
                                              slug='taqinor-ntmob30')
        self.user = CustomUser.objects.create_user(
            username='tech-ntmob30', password='x', company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    def test_renvoie_le_texte_transcrit(self):
        with patch('apps.chat.tasks._call_transcribe',
                   return_value={'enabled': True, 'text': ' Fuite au niveau du coffret ',
                                 'lang': 'fr'}):
            resp = self.api.post(URL, {'file': audio()}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['enabled'])
        self.assertEqual(resp.data['texte'], 'Fuite au niveau du coffret')

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=False)
    def test_desactivee_repond_enabled_false_sans_appeler_le_service(self):
        with patch('apps.chat.tasks._call_transcribe') as mock_call:
            resp = self.api.post(URL, {'file': audio()}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['enabled'])
        mock_call.assert_not_called()

    @override_settings(CHAT_TRANSCRIPTION_ENABLED=True)
    def test_panne_du_service_nest_jamais_bloquante(self):
        with patch('apps.chat.tasks._call_transcribe',
                   side_effect=RuntimeError('service muet')):
            resp = self.api.post(URL, {'file': audio()}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['enabled'])

    def test_sans_fichier_400(self):
        self.assertEqual(self.api.post(URL, {}, format='multipart').status_code, 400)

    def test_anonyme_refuse(self):
        anon = APIClient()
        self.assertIn(anon.post(URL, {'file': audio()}, format='multipart').status_code,
                      (401, 403))
