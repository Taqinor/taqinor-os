"""NTAI12 — Tests du compte rendu d'intervention dicté (voix → CR structuré).

Couvre : garde-fous d'upload repris de l'OCR (taille + octets magiques),
dégradation propre sans clé STT, structuration en 4 sections avec un faux LLM,
NON-PERSISTANCE de l'audio, et le fait que le STATUT du ticket n'est jamais
touché.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, STTProvider, register_provider
from core.ai import registry

from ..services import CR_SECTIONS, _detect_audio_mime, _parse_cr_json

User = get_user_model()

URL = '/api/django/ai/cr-intervention/'

#: Un conteneur OGG minimal — seuls les octets magiques comptent ici.
AUDIO_OGG = b'OggS' + b'\x00' * 60


class FakeSTT(STTProvider):
    key = 'fake_ntai12_stt'
    last_mime = None

    def is_configured(self):
        return True

    def transcribe(self, *, content, mime_type, language='fr'):
        FakeSTT.last_mime = mime_type
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': "Onduleur en défaut d'isolement, remplacé le "
                          'parafoudre, prévoir un contrôle dans six mois.'})


class FakeCrLLM(LLMProvider):
    key = 'fake_ntai12_llm'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system='', max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key, data={
            'text': '{"diagnostic": "Défaut d\'isolement onduleur", '
                    '"travaux": "Remplacement du parafoudre", '
                    '"pieces": "Parafoudre DC", '
                    '"recommandations": "Contrôle dans 6 mois"}'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def audio_upload(content=AUDIO_OGG, name='memo.ogg'):
    return SimpleUploadedFile(name, content, content_type='audio/ogg')


class Ntai12CrInterventionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client
        from apps.sav.models import Ticket

        cls.company = make_company('ntai12-co', 'NTAI12 Co')
        # Garde CI : la seconde société porte un slug distinct explicite.
        cls.autre = make_company('ntai12-autre', 'NTAI12 Autre')
        cls.user = User.objects.create_user(
            username='ntai12-user', password='x', company=cls.company,
            role_legacy='normal')
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client NTAI12')
        cls.ticket = Ticket.objects.create(
            company=cls.company, reference='SAV-NTAI12-1',
            client=cls.client_obj, statut='en_cours')
        cls.client_autre = Client.objects.create(
            company=cls.autre, nom='Client autre')
        cls.ticket_autre = Ticket.objects.create(
            company=cls.autre, reference='SAV-NTAI12-2',
            client=cls.client_autre, statut='nouveau')

    def _with_stt(self, *, llm=False):
        register_provider(FakeSTT)
        self.addCleanup(
            lambda: registry._REGISTRY['stt'].pop('fake_ntai12_stt', None))
        providers = {'stt': 'fake_ntai12_stt'}
        if llm:
            register_provider(FakeCrLLM)
            self.addCleanup(
                lambda: registry._REGISTRY['llm'].pop('fake_ntai12_llm', None))
            providers['llm'] = 'fake_ntai12_llm'
        return override_settings(AI_PROVIDERS=providers)

    # ── Garde-fous d'upload ─────────────────────────────────────────────────
    def test_fichier_absent_400(self):
        resp = auth(self.user).post(URL, {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_format_non_reconnu_400(self):
        resp = auth(self.user).post(
            URL, {'file': audio_upload(b'PAS DU TOUT DE L AUDIO' * 4)},
            format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Format audio', resp.data['detail'])

    def test_fichier_trop_gros_refuse(self):
        # Garde vérifiée au niveau du SERVICE (pas d'upload de 20 Mo dans la
        # suite de tests) : la vue ne fait que lui passer les octets.
        from ..services import (CR_AUDIO_MAX_BYTES, AiCopiloteUnavailable,
                                cr_intervention_depuis_audio)

        with self.assertRaises(AiCopiloteUnavailable) as ctx:
            cr_intervention_depuis_audio(
                company=self.company,
                file_bytes=b'\x00' * (CR_AUDIO_MAX_BYTES + 1))
        self.assertIn('volumineux', str(ctx.exception))

    def test_detection_magic_bytes(self):
        self.assertEqual(_detect_audio_mime(b'OggS' + b'\x00' * 8), 'audio/ogg')
        self.assertEqual(_detect_audio_mime(b'RIFF' + b'\x00' * 4 + b'WAVE'),
                         'audio/wav')
        self.assertEqual(_detect_audio_mime(b'ID3' + b'\x00' * 9), 'audio/mpeg')
        self.assertEqual(_detect_audio_mime(b'\x00' * 4 + b'ftyp' + b'\x00' * 4),
                         'audio/mp4')
        self.assertIsNone(_detect_audio_mime(b'%PDF-1.7\x00\x00\x00\x00'))

    def test_anonyme_refuse(self):
        resp = APIClient().post(URL, {'file': audio_upload()},
                                format='multipart')
        self.assertIn(resp.status_code, (401, 403))

    # ── Dégradation sans clé STT ────────────────────────────────────────────
    def test_sans_cle_stt_degrade_en_503(self):
        resp = auth(self.user).post(URL, {'file': audio_upload()},
                                    format='multipart')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('transcription', resp.data['detail'])

    # ── Chemin câblé ────────────────────────────────────────────────────────
    def test_cr_structure_en_quatre_sections(self):
        with self._with_stt(llm=True):
            resp = auth(self.user).post(
                URL, {'file': audio_upload(), 'ticket_id': self.ticket.id},
                format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['structure'])
        self.assertEqual(set(resp.data['cr']), set(CR_SECTIONS))
        self.assertIn('parafoudre', resp.data['cr']['travaux'].lower())
        self.assertEqual(resp.data['ticket_id'], self.ticket.id)
        self.assertFalse(resp.data['applique'])
        # Le MIME transmis au STT vient des octets, pas du Content-Type client.
        self.assertEqual(FakeSTT.last_mime, 'audio/ogg')

    def test_sans_llm_le_transcript_reste_utilisable(self):
        with self._with_stt():
            resp = auth(self.user).post(URL, {'file': audio_upload()},
                                        format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['structure'])
        self.assertIn('parafoudre', resp.data['cr']['diagnostic'])

    # ── Aucune écriture, aucun statut changé, aucun audio persisté ──────────
    def test_statut_du_ticket_inchange(self):
        with self._with_stt(llm=True):
            auth(self.user).post(
                URL, {'file': audio_upload(), 'ticket_id': self.ticket.id},
                format='multipart')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, 'en_cours')

    def test_audio_non_persiste(self):
        from apps.records.models import Attachment

        avant = Attachment.objects.count()
        with self._with_stt(llm=True):
            auth(self.user).post(
                URL, {'file': audio_upload(), 'ticket_id': self.ticket.id},
                format='multipart')
        self.assertEqual(Attachment.objects.count(), avant)

    # ── Scoping société ─────────────────────────────────────────────────────
    def test_ticket_autre_societe_refuse(self):
        with self._with_stt(llm=True):
            resp = auth(self.user).post(
                URL, {'file': audio_upload(),
                      'ticket_id': self.ticket_autre.id}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('introuvable', resp.data['detail'])

    # ── Parsing tolérant ────────────────────────────────────────────────────
    def test_parse_cr_json_tolere_du_texte_autour(self):
        cr = _parse_cr_json('Voici le JSON :\n{"diagnostic": "OK"}\nMerci.')
        self.assertEqual(cr['diagnostic'], 'OK')
        self.assertEqual(set(cr), set(CR_SECTIONS))

    def test_parse_cr_json_sans_json_ne_leve_pas(self):
        cr = _parse_cr_json('pas de json du tout')
        self.assertEqual(cr['diagnostic'], 'pas de json du tout')
        self.assertEqual(cr['travaux'], '')
