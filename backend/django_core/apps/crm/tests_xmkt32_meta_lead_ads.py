"""XMKT32 — Sync Meta Lead Ads → leads CRM (gated, API officielle simulée).

Couvre :
  - sans jeton configuré : GET de vérification → 404, POST → no-op 200 (rien
    n'est créé) ;
  - GET de vérification avec le bon hub.verify_token → renvoie hub.challenge ;
  - GET avec un mauvais token → 403 ;
  - POST simulé (Graph API mocké) → lead créé, attribué (canal META_ADS,
    utm_source=facebook, utm_campaign/utm_content = campagne/adset) ;
  - un second POST avec le MÊME leadgen_id (retry Meta) ne crée pas de
    deuxième lead (idempotence sur leadgen_id) ;
  - un prospect déjà connu (même téléphone) absorbe la touche Meta Lead Ads
    dans le lead existant au lieu d'en créer un second (QJ8) ;
  - aucun scraping : la récupération passe par ``fetch_meta_lead_data``
    (Graph API officiel), jamais par un fetch de page HTML.
  - PUB26 — signature HMAC ``X-Hub-Signature-256`` : bien formée → traité ;
    mal signée → 403 ; secret absent → accepté quand même (rétro-compat).
"""
import hashlib
import hmac
import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import Lead

VERIFY_TOKEN = 'test-verify-token'
ACCESS_TOKEN = 'test-access-token'
APP_SECRET = 'test-app-secret'


def _sign(secret, body: bytes) -> str:
    return 'sha256=' + hmac.new(
        secret.encode(), body, hashlib.sha256).hexdigest()


def _lead_data(leadgen_id='1001', nom='Yassine Bennani',
               telephone='+212661112233', email='yassine@example.com',
               ville='Casablanca'):
    return {
        'field_data': [
            {'name': 'full_name', 'values': [nom]},
            {'name': 'phone_number', 'values': [telephone]},
            {'name': 'email', 'values': [email]},
            {'name': 'city', 'values': [ville]},
        ]
    }


def _notification_payload(leadgen_id='1001', ad_id='', adgroup_id='',
                          form_id=''):
    # ADSENG1 — le webhook leadgen de Meta pousse UNIQUEMENT des clés de
    # jointure stables (ad_id/adgroup_id/form_id), JAMAIS campaign_name/
    # adset_name : les noms lisibles sont résolus côté ERP via les miroirs
    # adsengine. Ce payload reflète donc la vraie forme Meta.
    return {
        'entry': [{
            'changes': [{
                'field': 'leadgen',
                'value': {
                    'leadgen_id': leadgen_id,
                    'ad_id': ad_id,
                    'adgroup_id': adgroup_id,
                    'form_id': form_id,
                },
            }]
        }]
    }


class MetaLeadAdsUnconfiguredTests(TestCase):
    """Sans jeton configuré : 404/no-op — jamais d'exception."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Off', slug='taqinor-meta-off')
        self.url = reverse('meta-lead-ads-webhook')

    @override_settings(META_LEAD_ADS_VERIFY_TOKEN='', META_LEAD_ADS_ACCESS_TOKEN='')
    def test_get_verification_404_without_verify_token(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': 'anything',
            'hub.challenge': 'chal123'})
        self.assertEqual(resp.status_code, 404)

    @override_settings(META_LEAD_ADS_VERIFY_TOKEN='', META_LEAD_ADS_ACCESS_TOKEN='')
    def test_post_noop_without_access_token(self):
        resp = self.client.post(
            self.url, data=json.dumps(_notification_payload()),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)


@override_settings(META_LEAD_ADS_VERIFY_TOKEN=VERIFY_TOKEN)
class MetaLeadAdsVerificationTests(TestCase):
    def setUp(self):
        self.url = reverse('meta-lead-ads-webhook')

    def test_correct_token_returns_challenge(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': VERIFY_TOKEN,
            'hub.challenge': 'chal-xyz'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'chal-xyz')

    def test_wrong_token_is_refused(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe', 'hub.verify_token': 'wrong',
            'hub.challenge': 'chal-xyz'})
        self.assertEqual(resp.status_code, 403)


@override_settings(META_LEAD_ADS_ACCESS_TOKEN=ACCESS_TOKEN)
class MetaLeadAdsIngestTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta On', slug='taqinor-meta-on')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload),
            content_type='application/json')

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_simulated_payload_creates_attributed_lead(self, fetch_mock):
        """Payload Lead Ads simulé (API officielle mockée) → lead créé,
        attribué canal META_ADS + utm_source facebook ; le NOM de campagne est
        résolu via les miroirs adsengine (ADSENG1 : Meta ne pousse que
        ad_id/adgroup_id), utm_content = ad-<ad_id> (convention ADSENG23)."""
        from apps.adsengine.models import AdCampaignMirror, AdSetMirror
        campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='CMP-1', name='Campagne Été',
            status='PAUSED')
        AdSetMirror.objects.create(
            company=self.company, meta_id='ASET-1', name='Adset Casablanca',
            campaign=campaign)
        fetch_mock.return_value = _lead_data(leadgen_id='2001')
        resp = self._post(_notification_payload(
            leadgen_id='2001', ad_id='AD-2001', adgroup_id='ASET-1',
            form_id='FORM-1'))
        self.assertEqual(resp.status_code, 200)
        fetch_mock.assert_called_once_with('2001', ACCESS_TOKEN)

        lead = Lead.objects.get(company=self.company)
        self.assertEqual(lead.canal, Lead.Canal.META_ADS)
        self.assertEqual(lead.source, Lead.Source.META_LEAD_ADS)
        self.assertEqual(lead.utm_source, 'facebook')
        # Nom de campagne résolu localement via le miroir (ad_id/adgroup_id).
        self.assertEqual(lead.utm_campaign, 'Campagne Été')
        # Convention ADSENG23 : utm_content = ad-<ad_id>, jamais l'adset_name.
        self.assertEqual(lead.utm_content, 'ad-AD-2001')
        self.assertEqual(lead.external_system, 'meta_lead_ads')
        self.assertEqual(lead.external_id, '2001')
        self.assertEqual(lead.nom, 'Yassine Bennani')

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_duplicate_leadgen_id_is_absorbed_not_duplicated(self, fetch_mock):
        """Un retry Meta (même leadgen_id) ne crée pas un deuxième lead."""
        fetch_mock.return_value = _lead_data(leadgen_id='3001')
        self._post(_notification_payload(leadgen_id='3001'))
        self._post(_notification_payload(leadgen_id='3001'))
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_known_contact_absorbs_into_existing_lead(self, fetch_mock):
        """QJ8 : un prospect déjà connu (même téléphone, autre canal) absorbe
        la touche Meta Lead Ads dans son lead existant."""
        existing = Lead.objects.create(
            company=self.company, nom='Yassine Ancien',
            telephone='+212661112233', canal=Lead.Canal.TELEPHONE)
        fetch_mock.return_value = _lead_data(
            leadgen_id='4001', telephone='+212661112233')
        resp = self._post(_notification_payload(leadgen_id='4001'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.external_id, '4001')

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_fetch_failure_is_skipped_not_fatal(self, fetch_mock):
        """Un échec de récupération Graph API pour UN lead n'empêche pas la
        réponse 200 (jamais d'exception au webhook)."""
        fetch_mock.side_effect = Exception('boom')
        resp = self._post(_notification_payload(leadgen_id='5001'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)


@override_settings(
    META_LEAD_ADS_ACCESS_TOKEN=ACCESS_TOKEN, META_LEAD_ADS_APP_SECRET=APP_SECRET)
class MetaLeadAdsSignatureTests(TestCase):
    """PUB26 — vérification HMAC ``X-Hub-Signature-256`` du POST de notification."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Sig', slug='taqinor-meta-sig')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload, *, signature=None):
        body = json.dumps(payload).encode('utf-8')
        headers = {}
        if signature is not None:
            headers['HTTP_X_HUB_SIGNATURE_256'] = signature
        return self.client.post(
            self.url, data=body, content_type='application/json', **headers)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_valid_signature_is_processed(self, fetch_mock):
        fetch_mock.return_value = _lead_data(leadgen_id='6001')
        payload = _notification_payload(leadgen_id='6001')
        body = json.dumps(payload).encode('utf-8')
        resp = self._post(payload, signature=_sign(APP_SECRET, body))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)

    def test_missing_signature_is_rejected_403(self):
        resp = self._post(_notification_payload(leadgen_id='6002'))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    def test_wrong_signature_is_rejected_403(self):
        resp = self._post(
            _notification_payload(leadgen_id='6003'),
            signature='sha256=' + ('0' * 64))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    @override_settings(META_LEAD_ADS_APP_SECRET='')
    def test_absent_secret_stays_backward_compatible(self, fetch_mock):
        """Secret non configuré : le webhook reste ouvert (comportement
        historique préservé) — un warning est loggué mais rien n'est bloqué."""
        fetch_mock.return_value = _lead_data(leadgen_id='6004')
        resp = self._post(_notification_payload(leadgen_id='6004'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)


@override_settings(META_LEAD_ADS_ACCESS_TOKEN='')
class MetaLeadAdsConnectionFallbackTests(TestCase):
    """FIXPUB1 — sans ``META_LEAD_ADS_ACCESS_TOKEN`` (env), le webhook utilise le
    token de la ``MetaConnection`` activée de la société ; l'env, quand présent,
    gagne toujours. Corrige le compte historique qui n'a QU'une connexion
    tokenisée (pas d'env) et dont la capture ne partait jamais."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Meta Conn', slug='taqinor-meta-conn')
        from apps.adsengine.models import MetaConnection
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'CONN-TOKEN'}, ad_account_id='act_7')
        self.url = reverse('meta-lead-ads-webhook')

    def _post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload),
            content_type='application/json')

    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_uses_connection_token_when_env_absent(self, fetch_mock):
        """Sans env : le fetch Graph API part avec le token de la connexion."""
        fetch_mock.return_value = _lead_data(leadgen_id='7001')
        resp = self._post(_notification_payload(leadgen_id='7001'))
        self.assertEqual(resp.status_code, 200)
        fetch_mock.assert_called_once_with('7001', 'CONN-TOKEN')
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='ENV-TOKEN')
    @mock.patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_env_token_wins_over_connection(self, fetch_mock):
        """Env présent : il l'emporte sur le token de la connexion."""
        fetch_mock.return_value = _lead_data(leadgen_id='7002')
        resp = self._post(_notification_payload(leadgen_id='7002'))
        self.assertEqual(resp.status_code, 200)
        fetch_mock.assert_called_once_with('7002', 'ENV-TOKEN')


class FetchMetaLeadDataVersionTests(TestCase):
    """Garde anti-dérive : le fetch Graph du webhook suit la SOURCE UNIQUE de
    version (apps.adsengine.api_version), jamais une version codée en dur —
    la v19.0 restée ici était morte depuis 02/2025 (même dérive que l'émetteur
    CAPI ventes avant ADSENG2)."""

    def test_fetch_builds_url_from_shared_graph_base(self):
        from unittest.mock import patch

        from apps.adsengine.api_version import GRAPH_BASE_URL
        from apps.crm.webhooks import fetch_meta_lead_data

        seen = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"field_data": []}'

        def fake_urlopen(url, timeout=None):
            seen['url'] = url
            return _Resp()

        with patch('urllib.request.urlopen', fake_urlopen):
            data = fetch_meta_lead_data('42', 'tok')
        self.assertEqual(data, {'field_data': []})
        self.assertTrue(
            seen['url'].startswith(f'{GRAPH_BASE_URL}/42'),
            msg=f"URL Graph inattendue : {seen['url']}")
        self.assertNotIn('v19.0', seen['url'])
