"""NTMAR5 — Générateur de facture électronique au schéma DGI (flag, dry-run).

Critère : flag OFF -> l'app est inerte ; flag ON en mode=dry_run -> un XML
conforme est produit et stocké, statut=genere, aucune transmission.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.einvoice import services
from apps.einvoice.models import FactureElectronique

from ._fixtures import make_company, make_facture, seller_profile


def _fake_minio_client():
    return MagicMock()


class GenererFlagOffTests(TestCase):
    def setUp(self):
        self.company = make_company('einvoice-off', 'EInvoice Off')
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-OFF-0001')

    @override_settings(EINVOICE_ENABLED=False)
    def test_flag_off_is_a_noop(self):
        result = services.generer(self.facture.id, self.company)
        self.assertIsNone(result)
        self.assertEqual(FactureElectronique.objects.count(), 0)


class GenererFlagOnTests(TestCase):
    def setUp(self):
        self.company = make_company('einvoice-on', 'EInvoice On')
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-ON-0001')

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._minio_client', side_effect=_fake_minio_client)
    def test_flag_on_generates_conform_xml_dry_run(self, _mock_client):
        fe = services.generer(self.facture.id, self.company)
        self.assertIsNotNone(fe)
        self.assertEqual(fe.statut, FactureElectronique.Statut.GENERE)
        self.assertEqual(fe.mode, FactureElectronique.Mode.DRY_RUN)
        self.assertEqual(fe.version, 1)
        self.assertEqual(fe.facture_ref, 'FAC-ON-0001')
        self.assertTrue(fe.hash_contenu)
        self.assertTrue(fe.xml_key.startswith(f'einvoice/{self.company.id}/'))

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._minio_client', side_effect=_fake_minio_client)
    def test_never_transmitted_on_generation(self, _mock_client):
        fe = services.generer(self.facture.id, self.company)
        self.assertNotEqual(fe.statut, FactureElectronique.Statut.TRANSMIS)
        self.assertNotEqual(fe.statut, FactureElectronique.Statut.SIGNE)

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._minio_client', side_effect=_fake_minio_client)
    def test_unknown_facture_raises(self, _mock_client):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.generer(999999, self.company)

    @override_settings(EINVOICE_ENABLED=True)
    @patch('apps.einvoice.services._minio_client', side_effect=_fake_minio_client)
    def test_scoped_to_company(self, _mock_client):
        other = make_company('einvoice-other', 'EInvoice Other')
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.generer(self.facture.id, other)
