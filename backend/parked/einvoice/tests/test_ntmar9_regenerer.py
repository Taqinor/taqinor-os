"""NTMAR9 — Journal & re-génération idempotente e-invoice.

Critère : deux régénérations produisent deux versions horodatées, le contenu
original reste téléchargeable.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.einvoice import services
from apps.einvoice.models import FactureElectronique

from ._fixtures import make_company, make_facture, make_user, seller_profile


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RegenererServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('einvoice-regen', 'EInvoice Regen')
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-REGEN-0001')

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._minio_client',
           side_effect=lambda: MagicMock())
    def test_two_regenerations_produce_two_immutable_versions(self, _mock):
        fe1 = services.generer(self.facture.id, self.company)
        fe2 = services.regenerer(fe1)
        self.assertEqual(fe1.version, 1)
        self.assertEqual(fe2.version, 2)
        self.assertNotEqual(fe1.id, fe2.id)
        # Le contenu original reste accessible (ligne non écrasée).
        original = FactureElectronique.objects.get(id=fe1.id)
        self.assertEqual(original.version, 1)
        self.assertEqual(original.xml_key, fe1.xml_key)


class TelechargerApiTests(TestCase):
    ENDPOINT = '/api/django/einvoice/factures-electroniques/'

    def setUp(self):
        self.company = make_company('einvoice-dl', 'EInvoice DL')
        self.user = make_user(self.company, 'einv-dl')
        self.api = auth(self.user)
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-DL-0001')

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._download_xml')
    @patch('apps.einvoice.services._minio_client',
           side_effect=lambda: MagicMock())
    def test_download_streams_xml_nosniff(self, _mock_client, mock_download):
        fe = services.generer(self.facture.id, self.company)
        mock_download.return_value = '<Invoice>test</Invoice>'
        resp = self.api.get(f'{self.ENDPOINT}{fe.id}/telecharger/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp['Content-Type'], 'application/xml')
        self.assertEqual(resp['X-Content-Type-Options'], 'nosniff')

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._minio_client',
           side_effect=lambda: MagicMock())
    def test_regenerer_action_creates_new_version(self, _mock_client):
        fe = services.generer(self.facture.id, self.company)
        resp = self.api.post(f'{self.ENDPOINT}{fe.id}/regenerer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['version'], 2)
