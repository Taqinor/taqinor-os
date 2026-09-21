"""NTMAR6 — Emplacement de signature électronique (scaffold, non câblé).

Critère : ``preparer_signature`` renvoie l'empreinte + laisse ``statut=genere``,
jamais ``signe``, sans provider réel.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.einvoice import services
from apps.einvoice.models import FactureElectronique

from ._fixtures import make_company, make_facture, seller_profile


class PreparerSignatureTests(TestCase):
    def setUp(self):
        self.company = make_company('einvoice-sig', 'EInvoice Sig')
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-SIG-0001')
        with override_settings(EINVOICE_ENABLED=True), \
                patch('apps.einvoice.services._minio_client',
                      side_effect=lambda: MagicMock()):
            self.fe = services.generer(self.facture.id, self.company)

    def test_default_provider_is_noop_and_never_signs(self):
        result = services.preparer_signature(self.fe)
        self.assertEqual(result['provider'], 'noop')
        self.assertFalse(result['signe'])
        self.assertTrue(result['empreinte'])
        self.fe.refresh_from_db()
        self.assertEqual(self.fe.statut, FactureElectronique.Statut.GENERE)
        self.assertIsNone(self.fe.signe_le)

    @override_settings(EINVOICE_SIGNATURE_PROVIDER='future_provider')
    def test_unknown_provider_still_never_signs(self):
        result = services.preparer_signature(self.fe)
        self.assertFalse(result['signe'])
        self.fe.refresh_from_db()
        self.assertEqual(self.fe.statut, FactureElectronique.Statut.GENERE)
