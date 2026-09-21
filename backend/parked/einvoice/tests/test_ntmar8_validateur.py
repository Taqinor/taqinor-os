"""NTMAR8 — Validateur pré-transmission (contrôles DGI durs).

Critère : une facture non conforme renvoie >= 1 anomalie ; une facture
conforme renvoie liste vide.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.einvoice import services
from apps.einvoice.validators import controler_avant_transmission

from ._fixtures import make_company, make_facture, seller_profile


class ControlerAvantTransmissionTests(TestCase):
    def setUp(self):
        self.company = make_company('einvoice-val', 'EInvoice Val')
        seller_profile(self.company)

    def _generer(self, facture):
        with override_settings(EINVOICE_ENABLED=True), \
                patch('apps.einvoice.services._minio_client',
                      side_effect=lambda: MagicMock()):
            return services.generer(facture.id, self.company)

    def test_conform_facture_has_no_anomalies(self):
        facture = make_facture(self.company, reference='FAC-VAL-0001')
        fe = self._generer(facture)
        anomalies = controler_avant_transmission(fe)
        self.assertEqual(anomalies, [])

    def test_missing_client_ice_b2b_is_flagged(self):
        facture = make_facture(
            self.company, reference='FAC-VAL-0002', ice_client='')
        fe = self._generer(facture)
        anomalies = controler_avant_transmission(fe)
        self.assertTrue(
            any('ICE du client' in a for a in anomalies), anomalies)

    def test_no_xml_generated_is_flagged(self):
        facture = make_facture(self.company, reference='FAC-VAL-0003')
        # Ligne créée en 'brouillon' local (pas via generer()) : aucun XML.
        from apps.einvoice.models import FactureElectronique
        fe = FactureElectronique.objects.create(
            company=self.company, facture_id=facture.id,
            facture_ref=facture.reference)
        anomalies = controler_avant_transmission(fe)
        self.assertTrue(any('Aucun XML' in a for a in anomalies), anomalies)
