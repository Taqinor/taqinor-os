"""NTFPA12 — driver carnet de commandes → revenu engagé : agrège les devis
acceptés non facturés par mois."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis
from apps.fpa.selectors import revenu_engage_carnet


class TestRevenuEngageCarnet(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa12-co', defaults={'nom': 'NTFPA12 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')

    def _devis_accepte(self, date_acceptation, montant):
        self._ref_seq = getattr(self, '_ref_seq', 0) + 1
        devis = Devis.objects.create(
            company=self.company, client=self.client_obj,
            reference=f'DEV-NTFPA12-{self._ref_seq:04d}',
            statut=Devis.Statut.ACCEPTE, date_acceptation=date_acceptation)
        LigneDevis.objects.create(
            devis=devis, designation='Panneau', quantite=1,
            prix_unitaire=Decimal(montant), taux_tva=Decimal('20'))
        return devis

    def test_carnet_par_mois(self):
        d1 = self._devis_accepte(date(2027, 3, 10), '10000')
        d2 = self._devis_accepte(date(2027, 3, 20), '5000')
        par_mois = revenu_engage_carnet(
            self.company, date(2027, 1, 1), date(2027, 12, 31))
        self.assertIn('2027-03', par_mois)
        attendu = Decimal(str(d1.total_ttc or 0)) + Decimal(str(d2.total_ttc or 0))
        self.assertEqual(par_mois['2027-03'], attendu)
        self.assertGreater(par_mois['2027-03'], Decimal('0'))

    def test_hors_fenetre_exclu(self):
        self._devis_accepte(date(2028, 1, 10), '10000')
        par_mois = revenu_engage_carnet(
            self.company, date(2027, 1, 1), date(2027, 12, 31))
        self.assertEqual(par_mois, {})
