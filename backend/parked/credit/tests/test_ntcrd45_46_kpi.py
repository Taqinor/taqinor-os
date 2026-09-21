"""NTCRD45/46 — KPI crédit : DSO pondéré risque + répartition score
(NTCRD45) et taux de dérogations approuvées (NTCRD46), exposés comme provider
KPI fédéré (ARC40)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import DerogationCredit
from apps.credit.selectors import kpi_credit
from apps.credit.services import approuver_derogation
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd45-co', nom='NTCRD45 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD45And46KpiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd45_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd45@example.com')
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N45001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('10000'), created_by=self.admin)

    def test_kpi_tiles_shape(self):
        tuiles = kpi_credit(self.company)
        ids = {t['id'] for t in tuiles}
        self.assertIn('credit_dso_pondere', ids)
        self.assertIn('credit_taux_derogations', ids)
        # Chaque tuile normalisée porte id/label/valeur.
        for t in tuiles:
            self.assertIn('id', t)
            self.assertIn('label', t)
            self.assertIn('valeur', t)

    def test_declared_as_kpi_provider(self):
        from apps.credit.platform import PLATFORM
        self.assertIn(
            'apps.credit.selectors.kpi_credit', PLATFORM['kpi_providers'])

    def test_taux_derogations(self):
        # 2 demandes, 1 approuvée → taux 0.5.
        d1 = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('3000'))
        approuver_derogation(d1, self.admin)
        tuiles = {t['id']: t['valeur'] for t in kpi_credit(self.company)}
        self.assertEqual(tuiles['credit_taux_derogations'], 0.5)
