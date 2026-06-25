"""QJ9 — Tests de l'attribution first-touch + Meta CAPI.

Deux axes :
  1. _persist_attribution : copie UTM/fbclid du Lead vers etude_params du Devis
     à l'acceptation (lossless, idempotent, no migration).
  2. _fire_capi_signed_quote : dégrade en no-op quand META_CAPI_ACCESS_TOKEN est
     absent ; quand présent (mock) tente le POST HTTP vers l'API Meta.

Tests company-scoped : la copie d'attribution est toujours scopée au devis
et à son lead (multi-tenant par construction — FK Devis→Lead→Company).
"""
from unittest import mock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from authentication.models import Company

User = get_user_model()


def _make_company(slug='co-qj9'):
    return Company.objects.create(nom=slug, slug=slug)


def _make_user(company, username='v'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='responsable')


# ── _persist_attribution ──────────────────────────────────────────────────────

class PersistAttributionTests(TestCase):
    """Tests pour _persist_attribution (QJ9)."""

    def setUp(self):
        from apps.crm.models import Lead, Client
        self.company = _make_company()
        self.user = _make_user(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJ9')
        self.lead = Lead.objects.create(
            company=self.company,
            nom='Lead QJ9',
            telephone='0612000000',
            fbclid='fb.1.TEST.123',
            utm_source='facebook',
            utm_medium='cpc',
            utm_campaign='solar-2026',
            utm_content='banner-a',
            utm_term='panneau solaire',
        )

    def _make_devis(self, lead=None, etude_params=None):
        from apps.ventes.models import Devis
        return Devis.objects.create(
            company=self.company,
            client=self.client_obj,
            lead=lead,
            reference=f'DEV-QJ9-{Devis.objects.count() + 1}',
            etude_params=etude_params,
        )

    def test_attribution_copied_on_accept(self):
        """Les UTM/fbclid du lead sont copiés dans etude_params à l'acceptation."""
        from apps.ventes.services import _persist_attribution
        devis = self._make_devis(lead=self.lead)
        _persist_attribution(devis=devis)
        devis.refresh_from_db()
        attr = (devis.etude_params or {}).get('attribution', {})
        self.assertEqual(attr.get('fbclid'), 'fb.1.TEST.123')
        self.assertEqual(attr.get('utm_source'), 'facebook')
        self.assertEqual(attr.get('utm_medium'), 'cpc')
        self.assertEqual(attr.get('utm_campaign'), 'solar-2026')
        self.assertEqual(attr.get('utm_content'), 'banner-a')
        self.assertEqual(attr.get('utm_term'), 'panneau solaire')

    def test_idempotent_does_not_overwrite_existing_attribution(self):
        """Un appel redondant ne ré-écrit pas une attribution déjà présente."""
        from apps.ventes.services import _persist_attribution
        devis = self._make_devis(
            lead=self.lead,
            etude_params={'attribution': {'fbclid': 'ORIGINAL', 'utm_source': 'google'}},
        )
        _persist_attribution(devis=devis)
        devis.refresh_from_db()
        attr = (devis.etude_params or {}).get('attribution', {})
        # L'attribution ORIGINALE doit être préservée.
        self.assertEqual(attr.get('fbclid'), 'ORIGINAL')
        self.assertEqual(attr.get('utm_source'), 'google')

    def test_no_lead_is_noop(self):
        """Un devis sans lead ne lève pas d'exception et ne modifie rien."""
        from apps.ventes.services import _persist_attribution
        devis = self._make_devis(lead=None)
        _persist_attribution(devis=devis)
        devis.refresh_from_db()
        params = devis.etude_params or {}
        self.assertNotIn('attribution', params)

    def test_empty_attribution_fields_skipped(self):
        """Un lead sans UTM/fbclid ne crée pas de bloc attribution vide."""
        from apps.crm.models import Lead
        from apps.ventes.services import _persist_attribution
        lead_empty = Lead.objects.create(
            company=self.company, nom='Lead sans UTM')
        devis = self._make_devis(lead=lead_empty)
        _persist_attribution(devis=devis)
        devis.refresh_from_db()
        params = devis.etude_params or {}
        self.assertNotIn('attribution', params)

    def test_existing_etude_params_preserved(self):
        """Les autres clés d'etude_params ne sont pas écrasées."""
        from apps.ventes.services import _persist_attribution
        devis = self._make_devis(
            lead=self.lead,
            etude_params={'kw_crete': 5.4, 'production_kwh': 7800},
        )
        _persist_attribution(devis=devis)
        devis.refresh_from_db()
        params = devis.etude_params or {}
        self.assertEqual(params.get('kw_crete'), 5.4)
        self.assertIn('attribution', params)

    def test_company_scoped_via_fk(self):
        """La copie est naturellement scopée : lead et devis partagent la même société."""
        from apps.ventes.services import _persist_attribution
        devis = self._make_devis(lead=self.lead)
        _persist_attribution(devis=devis)
        devis.refresh_from_db()
        # Le devis et son lead doivent appartenir à la même société.
        self.assertEqual(devis.company, self.lead.company)


# ── _fire_capi_signed_quote ───────────────────────────────────────────────────

class FireCapiSignedQuoteTests(TestCase):
    """Tests pour _fire_capi_signed_quote (QJ9)."""

    def _make_devis_stub(self, lead=None):
        """Stub minimal (pas de DB) pour les tests CAPI."""
        stub = mock.Mock()
        stub.reference = 'DEV-CAPI-01'
        stub.lead = lead
        stub.client = None
        stub.client_id = None
        stub.etude_params = {}
        stub.total_ttc = 48500.0
        return stub

    @override_settings(META_CAPI_ACCESS_TOKEN='')
    def test_no_token_is_noop(self):
        """Sans META_CAPI_ACCESS_TOKEN aucun appel HTTP n'est émis."""
        from apps.ventes.services import _fire_capi_signed_quote
        devis_stub = self._make_devis_stub()
        with mock.patch('urllib.request.urlopen') as mock_open:
            _fire_capi_signed_quote(devis=devis_stub)
            mock_open.assert_not_called()

    @override_settings(META_CAPI_ACCESS_TOKEN='')
    def test_no_token_never_raises(self):
        """Sans token le call ne lève jamais d'exception."""
        from apps.ventes.services import _fire_capi_signed_quote
        devis_stub = self._make_devis_stub()
        try:
            _fire_capi_signed_quote(devis=devis_stub)
        except Exception as exc:
            self.fail(f'_fire_capi_signed_quote a levé une exception : {exc}')

    @override_settings(META_CAPI_ACCESS_TOKEN='TEST_TOKEN',
                       META_CAPI_PIXEL_ID='')
    def test_no_pixel_logs_only(self):
        """Avec token mais sans pixel ID, on loggue sans faire de HTTP."""
        from apps.ventes.services import _fire_capi_signed_quote
        devis_stub = self._make_devis_stub()
        with mock.patch('urllib.request.urlopen') as mock_open:
            _fire_capi_signed_quote(devis=devis_stub)
            mock_open.assert_not_called()

    @override_settings(META_CAPI_ACCESS_TOKEN='TEST_TOKEN',
                       META_CAPI_PIXEL_ID='123456789')
    def test_with_token_and_pixel_calls_http(self):
        """Avec token + pixel, un POST HTTP est tenté vers l'API Meta."""
        from apps.ventes.services import _fire_capi_signed_quote
        devis_stub = self._make_devis_stub()
        mock_resp = mock.MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"events_received": 1}'
        with mock.patch('urllib.request.urlopen', return_value=mock_resp) as mock_open:
            _fire_capi_signed_quote(devis=devis_stub)
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            self.assertIn('graph.facebook.com', call_args.full_url)
            self.assertIn('SignedQuote', call_args.data.decode())

    @override_settings(META_CAPI_ACCESS_TOKEN='TEST_TOKEN',
                       META_CAPI_PIXEL_ID='123456789')
    def test_attribution_included_in_payload(self):
        """Les champs fbclid/utm_source sont inclus dans le payload CAPI."""
        from apps.ventes.services import _fire_capi_signed_quote
        lead_stub = mock.Mock()
        lead_stub.fbclid = 'fb.1.ABC.XYZ'
        lead_stub.utm_source = 'facebook'
        lead_stub.utm_medium = 'cpc'
        lead_stub.utm_campaign = 'solar-q2'
        lead_stub.utm_content = None
        lead_stub.utm_term = None
        devis_stub = self._make_devis_stub(lead=lead_stub)
        devis_stub.etude_params = {
            'attribution': {
                'fbclid': 'fb.1.ABC.XYZ',
                'utm_source': 'facebook',
                'utm_campaign': 'solar-q2',
            }
        }
        captured_payload = {}

        def _capture(req, timeout=None):
            captured_payload['data'] = req.data
            mock_resp = mock.MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_resp.status = 200
            mock_resp.read.return_value = b'{}'
            return mock_resp

        with mock.patch('urllib.request.urlopen', side_effect=_capture):
            _fire_capi_signed_quote(devis=devis_stub)

        import json
        payload = json.loads(captured_payload['data'].decode())
        event = payload['data'][0]
        self.assertEqual(event['event_name'], 'SignedQuote')
        self.assertIn('utm_source', event['custom_data'])
        self.assertEqual(event['custom_data']['order_id'], 'DEV-CAPI-01')

    @override_settings(META_CAPI_ACCESS_TOKEN='TEST_TOKEN',
                       META_CAPI_PIXEL_ID='123456789')
    def test_http_failure_never_propagates(self):
        """Une erreur HTTP vers Meta ne doit jamais remonter à accept_devis."""
        from apps.ventes.services import _fire_capi_signed_quote
        devis_stub = self._make_devis_stub()
        with mock.patch('urllib.request.urlopen',
                        side_effect=OSError('connection refused')):
            try:
                _fire_capi_signed_quote(devis=devis_stub)
            except Exception as exc:
                self.fail(f'_fire_capi_signed_quote a propagé une exception : {exc}')
