"""XMKT36 — [DECISION] Export de segments vers audiences publicitaires Meta.

Couvre : hash SHA-256 conforme (email trim+minuscules, téléphone chiffres avec
indicatif 212) ; export d'un segment CONSENTI en audience (mock API, gated) ;
clients signés en liste d'exclusion ; no-op réseau strict sans jeton ;
consentement XMKT4 + suppression XMKT3 respectés ; AUCUNE création de
campagne publicitaire (le service ne connaît que /customaudiences).
"""
import hashlib
import io
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ConsentRecord

from apps.compta import services
from apps.crm.models import Client, Lead
from apps.marketing.models import SegmentMarketing, SuppressionMarketing

User = get_user_model()

ADS_ENV = {
    'META_ADS_ENABLED': '1',
    'META_ADS_TOKEN': 'fake-ads-token',
    'META_AD_ACCOUNT_ID': '99887766',
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _fake_urlopen_factory(responses):
    """Renvoie un faux ``urlopen`` : chaque appel consomme la réponse
    suivante de ``responses`` (dicts sérialisés JSON) et journalise l'URL."""
    calls = []

    def _fake(req, timeout=None):
        calls.append({
            'url': req.full_url,
            'body': json.loads(req.data.decode()) if req.data else {},
        })
        data = responses[min(len(calls) - 1, len(responses) - 1)]
        return io.BytesIO(json.dumps(data).encode())

    return _fake, calls


class HashConformeTests(TestCase):
    def test_email_hash_trim_minuscules(self):
        attendu = hashlib.sha256(b'reda@example.com').hexdigest()
        self.assertEqual(
            services.hash_identifiant_meta('  Reda@Example.COM ', genre='email'),
            attendu)

    def test_telephone_hash_indicatif_212(self):
        attendu = hashlib.sha256(b'212600000001').hexdigest()
        self.assertEqual(
            services.hash_identifiant_meta('0600000001', genre='telephone'),
            attendu)
        self.assertEqual(
            services.hash_identifiant_meta('+212600000001', genre='telephone'),
            attendu)

    def test_valeur_vide_jamais_hashee(self):
        self.assertEqual(services.hash_identifiant_meta('', genre='email'), '')
        self.assertEqual(
            services.hash_identifiant_meta(None, genre='telephone'), '')


class ExportSegmentTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt36', 'XMKT36 Co')
        self.user = make_user(self.co, 'xmkt36-user')
        self.lead = Lead.objects.create(
            company=self.co, nom='Alami', prenom='Sara', ville='Rabat',
            email='sara@example.com', telephone='+212600000010')
        self.client_signe = Client.objects.create(
            company=self.co, nom='ClientSigne', email='signe@example.com',
            telephone='+212600000011')
        self.segment = SegmentMarketing.objects.create(
            company=self.co, nom='Rabat froids', regles={'ville': 'Rabat'})

    def test_noop_reseau_strict_sans_jeton(self):
        with mock.patch('urllib.request.urlopen') as m_urlopen:
            resume = services.exporter_segment_audience_meta(self.segment)
            m_urlopen.assert_not_called()
        self.assertFalse(resume['configured'])
        self.assertEqual(resume['inclus'], 1)
        self.assertEqual(resume['exclus'], 1)
        self.assertEqual(resume['audience_id'], '')

    def test_export_avec_jeton_mock_api(self):
        fake, calls = _fake_urlopen_factory([
            {'id': 'aud_incl'}, {'num_received': 1},
            {'id': 'aud_excl'}, {'num_received': 1},
        ])
        with mock.patch.dict('os.environ', ADS_ENV), \
                mock.patch('urllib.request.urlopen', side_effect=fake):
            resume = services.exporter_segment_audience_meta(self.segment)
        self.assertTrue(resume['configured'])
        self.assertEqual(resume['audience_id'], 'aud_incl')
        self.assertEqual(resume['exclusion_audience_id'], 'aud_excl')
        self.assertEqual(resume['inclus'], 1)
        self.assertEqual(resume['exclus'], 1)
        # 4 appels : création audience + users, création exclusion + users.
        self.assertEqual(len(calls), 4)
        # Le payload users ne contient QUE des hashes hex (jamais de PII).
        users_call = calls[1]
        data_rows = users_call['body']['payload']['data']
        for row in data_rows:
            for value in row:
                if value:
                    self.assertRegex(value, r'^[0-9a-f]{64}$')
        # Hash de l'email du lead présent, jamais l'email en clair.
        email_hash = hashlib.sha256(b'sara@example.com').hexdigest()
        self.assertIn(email_hash, [v for row in data_rows for v in row])
        self.assertNotIn(
            'sara@example.com', json.dumps(users_call['body']))
        # AUCUNE création de campagne publicitaire (règle n°3) : seuls les
        # endpoints customaudiences/users sont touchés.
        for c in calls:
            self.assertNotIn('/campaigns', c['url'])
            self.assertNotIn('/adsets', c['url'])
            self.assertTrue(
                c['url'].endswith('/customaudiences')
                or c['url'].endswith('/users'),
                c['url'])

    def test_consentement_refuse_exclut_le_contact(self):
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='sara@example.com',
            purpose='marketing', granted=False)
        resume = services.exporter_segment_audience_meta(self.segment)
        self.assertEqual(resume['inclus'], 0)

    def test_suppression_exclut_le_contact(self):
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='sara@example.com',
            motif=SuppressionMarketing.Motif.DESINSCRIT)
        resume = services.exporter_segment_audience_meta(self.segment)
        self.assertEqual(resume['inclus'], 0)

    def test_sans_exclusions_demandees(self):
        resume = services.exporter_segment_audience_meta(
            self.segment, inclure_exclusions=False)
        self.assertEqual(resume['exclus'], 0)

    def test_endpoint_scoped_societe(self):
        other_co = make_company('xmkt36-b', 'XMKT36 B')
        other_user = make_user(other_co, 'xmkt36-user-b')
        api_b = auth(other_user)
        resp = api_b.post(
            f'/api/django/compta/segments-marketing/{self.segment.id}/'
            'exporter-audience-meta/')
        self.assertIn(resp.status_code, (403, 404))

    def test_endpoint_renvoie_resume(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/segments-marketing/{self.segment.id}/'
            'exporter-audience-meta/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['configured'])
        self.assertEqual(resp.data['inclus'], 1)
