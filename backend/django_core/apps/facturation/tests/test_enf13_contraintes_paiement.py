"""ENF13 — backstop DB des champs monétaires positifs de ``Paiement``
(``frais_rejet``, ``escompte_montant`` ; NULL toléré, ``montant`` reste signé).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_enf13_contraintes_paiement"
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase


class ContraintesPaiementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ENF13 Co', slug='enf13-paiement-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Enf13', prenom='Paiement',
            email='enf13-paiement@example.invalid')

    def _creer(self, **extra):
        from apps.ventes.models import Paiement
        with transaction.atomic():
            return Paiement.objects.create(
                company=self.company, client=self.client_obj,
                montant=Decimal('100.00'), date_paiement=date(2026, 10, 1),
                mode='virement', **extra)

    def test_frais_rejet_negatif_refuse(self):
        with self.assertRaises(IntegrityError):
            self._creer(frais_rejet=Decimal('-0.01'))

    def test_escompte_negatif_refuse(self):
        with self.assertRaises(IntegrityError):
            self._creer(escompte_montant=Decimal('-1'))

    def test_null_zero_et_positif_acceptes(self):
        self._creer()
        self._creer(frais_rejet=None, escompte_montant=None)
        p = self._creer(frais_rejet=Decimal('0'), escompte_montant=Decimal('5'))
        self.assertEqual(p.escompte_montant, Decimal('5'))

    def test_montant_negatif_reste_permis(self):
        """FG50 : la contre-passation d'un acompte est un Paiement négatif."""
        from apps.ventes.models import Paiement
        p = Paiement.objects.create(
            company=self.company, client=self.client_obj,
            montant=Decimal('-50.00'), date_paiement=date(2026, 10, 1),
            mode='virement')
        self.assertEqual(p.montant, Decimal('-50.00'))
