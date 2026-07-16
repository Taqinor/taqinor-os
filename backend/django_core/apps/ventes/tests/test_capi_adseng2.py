"""ADSENG2 — Tests du correctif émetteur CAPI SignedQuote.

Prouve :
  * l'URL cible la version COURANTE (v25, source unique partagée) — jamais la
    v19.0 codée en dur (expirée 02/2025) ;
  * l'événement porte un ``event_id`` DÉTERMINISTE (``signedquote:<reference>``)
    pour la dé-duplication 48 h ;
  * ``ip``/``user_agent`` (EMQ) sont threadés dans ``user_data`` quand fournis ;
  * la valeur reste le TTC remisé (non-régression QJ9) ;
  * la version est une SOURCE UNIQUE partagée avec le client Meta.
"""
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

MONTH = timezone.now().strftime('%Y%m')


def _mock_resp():
    resp = mock.MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = mock.Mock(return_value=False)
    resp.status = 200
    resp.read.return_value = b'{"events_received": 1}'
    return resp


class Adseng2CapiEmitterTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='adseng2-co', defaults={'nom': 'ADSENG2 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Capi',
            telephone='+212600000044')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-AE2C01',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('10.00'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='AE2-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))

    def _fire(self, **kwargs):
        from apps.ventes.services import _fire_capi_signed_quote
        with override_settings(META_CAPI_ACCESS_TOKEN='T',
                               META_CAPI_PIXEL_ID='999'):
            with mock.patch('urllib.request.urlopen',
                            return_value=_mock_resp()) as m:
                _fire_capi_signed_quote(devis=self.devis, **kwargs)
        req = m.call_args[0][0]
        return req.full_url, req.data.decode()

    def test_url_uses_current_api_version_not_v19(self):
        url, _body = self._fire()
        self.assertIn('/v25.0/', url)
        self.assertNotIn('v19.0', url)
        self.assertIn('/999/events', url)

    def test_event_has_deterministic_event_id(self):
        _url, body = self._fire()
        self.assertIn(f'signedquote:DEV-{MONTH}-AE2C01', body)
        self.assertIn('event_id', body)

    def test_emq_ip_and_user_agent_threaded(self):
        _url, body = self._fire(ip='41.92.10.5', user_agent='Mozilla/5.0 Test')
        self.assertIn('client_ip_address', body)
        self.assertIn('41.92.10.5', body)
        self.assertIn('client_user_agent', body)
        self.assertIn('Mozilla/5.0 Test', body)

    def test_emq_absent_when_not_provided(self):
        _url, body = self._fire()
        self.assertNotIn('client_ip_address', body)
        self.assertNotIn('client_user_agent', body)

    def test_value_still_discounted_ttc_non_regression(self):
        # 10000 HT − 10 % = 9000 HT ; TTC 10800 (jamais le brut 12000).
        _url, body = self._fire()
        self.assertIn('10800', body)
        self.assertNotIn('12000', body)


class Adseng2SharedVersionTests(SimpleTestCase):
    def test_version_is_single_source(self):
        from apps.adsengine.api_version import GRAPH_VERSION
        from apps.adsengine import meta_client
        # Le client Meta et l'émetteur CAPI partagent EXACTEMENT la même version.
        self.assertEqual(meta_client.GRAPH_VERSION, GRAPH_VERSION)
        self.assertEqual(GRAPH_VERSION, 'v25.0')
