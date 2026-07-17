"""NTMAR7 — Étend G14 : file d'attente de transmission Simpl (inerte, prête).

Critère : sans clé, ``transmettre`` laisse ``statut=en_attente`` et n'émet
aucune requête.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.einvoice import services
from apps.einvoice.models import TransmissionDGI

from ._fixtures import make_company, make_facture, seller_profile


class TransmettreTests(TestCase):
    def setUp(self):
        self.company = make_company('einvoice-tx', 'EInvoice Tx')
        seller_profile(self.company)
        self.facture = make_facture(self.company, reference='FAC-TX-0001')
        with override_settings(EINVOICE_ENABLED=True), \
                patch('apps.einvoice.services._minio_client',
                      side_effect=lambda: MagicMock()):
            self.fe = services.generer(self.facture.id, self.company)

    def test_disabled_by_default_stays_pending(self):
        transmission = services.transmettre(self.fe)
        self.assertEqual(transmission.statut, TransmissionDGI.Statut.EN_ATTENTE)
        self.assertEqual(transmission.tentatives, 0)

    @override_settings(DGI_TRANSMISSION_ENABLED=True, DGI_TRANSMISSION_URL='')
    def test_enabled_without_url_still_noops(self):
        transmission = services.transmettre(self.fe)
        self.assertEqual(transmission.statut, TransmissionDGI.Statut.EN_ATTENTE)

    def test_idempotent_get_or_create(self):
        t1 = services.transmettre(self.fe)
        t2 = services.transmettre(self.fe)
        self.assertEqual(t1.id, t2.id)
        self.assertEqual(TransmissionDGI.objects.filter(einvoice=self.fe).count(), 1)
