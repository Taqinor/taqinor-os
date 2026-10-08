"""APDF43 — les économies du portail lisent le tarif de Paramètres (plus de 1,40)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading
from apps.monitoring.selectors import client_environmental_dashboard
from apps.parametres.models import CompanyProfile


class TarifPortailTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='apdf43-co', defaults={'nom': 'APDF43 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='A',
            email='apdf43@example.invalid')
        inst = Installation.objects.create(
            company=self.company, reference='APDF43-1', client=self.client_obj,
            puissance_installee_kwc=Decimal('5'))
        ProductionReading.objects.create(
            company=self.company, installation=inst, date=date(2026, 6, 1),
            period_days=30, energy_kwh=Decimal('1000'))

    def test_tarif_societe(self):
        profile = CompanyProfile.get(company=self.company)
        profile.onee_tarif_kwh = Decimal('2.10')
        profile.save()
        d = client_environmental_dashboard(self.company, self.client_obj.id)
        self.assertEqual(d['tarif_mad_par_kwh'], Decimal('2.1'))
        self.assertEqual(d['economies_mad'], Decimal('2100.00'))

    def test_defaut_profil(self):
        d = client_environmental_dashboard(self.company, self.client_obj.id)
        self.assertEqual(d['economies_mad'], Decimal('1750.00'))
