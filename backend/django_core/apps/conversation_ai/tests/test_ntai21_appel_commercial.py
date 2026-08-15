"""NTAI21 — Tests des enregistrements d'appels commerciaux.

Couvre :
  * le téléversement crée un appel « non transcrit » rattaché au lead, société
    posée CÔTÉ SERVEUR (jamais lue du corps) ;
  * sans clé STT, la transcription est un no-op propre : statut inchangé,
    aucun octet lu du stockage, aucune erreur ;
  * avec un fournisseur STT factice, le transcript est stocké et la boucle de
    segmentation concatène les segments ;
  * un échec fournisseur est capturé (statut « erreur »), jamais levé ;
  * isolation multi-société (liste + rattachement d'un lead d'une autre
    société refusé) ;
  * la tâche Celery tolère un appel disparu.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from core.ai.providers import AIResult, STTProvider
from core.ai.registry import register_provider

from ..models import AppelCommercial
from ..services import decouper_audio, stt_configure, transcrire_appel
from ..tasks import transcrire_appel_task

User = get_user_model()

URL = '/api/django/conversation_ai/appels/'


class FauxSTT(STTProvider):
    """Fournisseur STT factice : ACTIF, local, aucun appel réseau."""

    key = 'faux_stt_ntai21'
    label = 'STT de test'

    def is_configured(self):
        return True

    def transcribe(self, *, content, mime_type, language='fr'):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': f'transcript de {len(content)} octets'})


class FauxSTTEnPanne(STTProvider):
    key = 'faux_stt_hs_ntai21'
    label = 'STT de test en panne'

    def is_configured(self):
        return True

    def transcribe(self, *, content, mime_type, language='fr'):
        return AIResult(ok=False, configured=True, provider=self.key,
                        error='fournisseur indisponible')


register_provider(FauxSTT)
register_provider(FauxSTTEnPanne)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai21UploadTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai21a', 'NTAI21 A')
        self.user = User.objects.create_user(
            username='ntai21a', password='x', company=self.co)
        self.lead = Lead.objects.create(company=self.co, nom='Prospect A')
        self.api = auth(self.user)

    def _fichier(self):
        return SimpleUploadedFile(
            'appel.mp3', b'ID3fake-audio-bytes', content_type='audio/mpeg')

    def test_upload_cree_un_appel_non_transcrit(self):
        with patch('apps.records.storage.store_attachment',
                   return_value=({'file_key': 'attachments/1/abc.mp3',
                                  'filename': 'appel.mp3', 'size': 18,
                                  'mime': 'audio/mpeg'}, None)):
            rep = self.api.post(
                URL, {'fichier': self._fichier(), 'lead': self.lead.id},
                format='multipart')
        self.assertEqual(rep.status_code, 201, rep.data)
        appel = AppelCommercial.objects.get(pk=rep.data['id'])
        self.assertEqual(appel.company_id, self.co.id)
        self.assertEqual(appel.lead_id, self.lead.id)
        self.assertEqual(appel.statut, AppelCommercial.STATUT_NON_TRANSCRIT)
        self.assertEqual(appel.fichier_key, 'attachments/1/abc.mp3')
        self.assertEqual(appel.transcript, '')

    def test_societe_jamais_lue_du_corps(self):
        autre = make_company('ntai21b', 'NTAI21 B')
        with patch('apps.records.storage.store_attachment',
                   return_value=({'file_key': 'attachments/1/abc.mp3',
                                  'filename': 'a.mp3', 'size': 18,
                                  'mime': 'audio/mpeg'}, None)):
            rep = self.api.post(
                URL, {'fichier': self._fichier(), 'company': autre.id},
                format='multipart')
        self.assertEqual(rep.status_code, 201, rep.data)
        appel = AppelCommercial.objects.get(pk=rep.data['id'])
        self.assertEqual(appel.company_id, self.co.id)

    def test_format_refuse_renvoie_400(self):
        with patch('apps.records.storage.store_attachment',
                   return_value=(None, 'Format audio non supporté')):
            rep = self.api.post(
                URL, {'fichier': self._fichier()}, format='multipart')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(AppelCommercial.objects.count(), 0)

    def test_lead_d_une_autre_societe_refuse(self):
        autre = make_company('ntai21c', 'NTAI21 C')
        lead_autre = Lead.objects.create(company=autre, nom='Prospect B')
        rep = self.api.post(
            URL, {'lead': lead_autre.id}, format='multipart')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('lead', rep.data)

    def test_liste_scopee_societe(self):
        AppelCommercial.objects.create(company=self.co, fichier_key='a')
        autre = make_company('ntai21d', 'NTAI21 D')
        AppelCommercial.objects.create(company=autre, fichier_key='b')
        rep = self.api.get(URL)
        self.assertEqual(rep.status_code, 200)
        resultats = rep.data['results'] if isinstance(rep.data, dict) else rep.data
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['fichier_key'], 'a')


class Ntai21TranscriptionTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai21e', 'NTAI21 E')
        self.appel = AppelCommercial.objects.create(
            company=self.co, fichier_key='attachments/1/appel.mp3',
            mime='audio/mpeg')

    def test_sans_cle_stt_no_op_propre(self):
        self.assertFalse(stt_configure())
        with patch('apps.records.storage.fetch_attachment') as lecture:
            self.assertFalse(transcrire_appel(self.appel))
        lecture.assert_not_called()
        self.appel.refresh_from_db()
        self.assertEqual(self.appel.statut,
                         AppelCommercial.STATUT_NON_TRANSCRIT)
        self.assertEqual(self.appel.transcript, '')

    @override_settings(AI_PROVIDERS={'stt': 'faux_stt_ntai21'})
    def test_avec_provider_le_transcript_est_stocke(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'0123456789', None)):
            self.assertTrue(transcrire_appel(self.appel))
        self.appel.refresh_from_db()
        self.assertEqual(self.appel.statut, AppelCommercial.STATUT_TRANSCRIT)
        self.assertEqual(self.appel.transcript, 'transcript de 10 octets')
        self.assertIsNotNone(self.appel.transcrit_le)

    @override_settings(AI_PROVIDERS={'stt': 'faux_stt_ntai21'})
    def test_segments_concatenes(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'0123456789', None)), \
                patch('apps.conversation_ai.services.decouper_audio',
                      return_value=[b'12', b'345']):
            transcrire_appel(self.appel)
        self.appel.refresh_from_db()
        self.assertEqual(
            self.appel.transcript,
            'transcript de 2 octets\ntranscript de 3 octets')

    @override_settings(AI_PROVIDERS={'stt': 'faux_stt_hs_ntai21'})
    def test_echec_fournisseur_capture(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'0123456789', None)):
            self.assertFalse(transcrire_appel(self.appel))
        self.appel.refresh_from_db()
        self.assertEqual(self.appel.statut, AppelCommercial.STATUT_ERREUR)
        self.assertIn('indisponible', self.appel.message)

    @override_settings(AI_PROVIDERS={'stt': 'faux_stt_ntai21'})
    def test_stockage_injoignable_capture(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(None, 'MinIO injoignable')):
            self.assertFalse(transcrire_appel(self.appel))
        self.appel.refresh_from_db()
        self.assertEqual(self.appel.statut, AppelCommercial.STATUT_ERREUR)

    def test_sans_fichier_aucune_transcription(self):
        appel = AppelCommercial.objects.create(company=self.co)
        self.assertFalse(transcrire_appel(appel))

    def test_decoupage_par_defaut_renvoie_l_audio_entier(self):
        self.assertEqual(decouper_audio(b'abc', 'audio/mpeg'), [b'abc'])
        self.assertEqual(decouper_audio(b'', 'audio/mpeg'), [])

    def test_tache_tolere_un_appel_disparu(self):
        self.assertIsNone(transcrire_appel_task(999999))

    def test_tache_sans_cle_laisse_non_transcrit(self):
        self.assertEqual(transcrire_appel_task(self.appel.id),
                         AppelCommercial.STATUT_NON_TRANSCRIT)
