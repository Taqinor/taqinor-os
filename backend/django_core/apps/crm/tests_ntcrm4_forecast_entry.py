"""NTCRM4 — Catégories de forecast (commit/best-case/pipeline/omis)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import ForecastEntry, Lead
from apps.roles.models import Role

User = get_user_model()


class ForecastEntryModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM4', slug='taqinor-ntcrm4')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.commercial = User.objects.create_user(
            username='com_ntcrm4', password='x', company=self.company, role=self.role)

    def test_lead_sans_forecast_entry_defaut_pipeline(self):
        lead = Lead.objects.create(company=self.company, nom='Lead sans forecast')
        self.assertFalse(ForecastEntry.objects.filter(lead=lead).exists())
        # PIPELINE est le défaut de catégorie quand une entrée est créée.
        entry = ForecastEntry.objects.create(company=self.company, lead=lead)
        self.assertEqual(entry.categorie, ForecastEntry.Categorie.PIPELINE)

    def test_montant_effectif_repli_sur_montant_estime(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead repli', montant_estime=Decimal('42000'))
        entry = ForecastEntry.objects.create(company=self.company, lead=lead)
        self.assertEqual(entry.montant_effectif, Decimal('42000'))

    def test_montant_prevu_explicite_prime(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead explicite', montant_estime=Decimal('1000'))
        entry = ForecastEntry.objects.create(
            company=self.company, lead=lead, montant_prevu=Decimal('9999'))
        self.assertEqual(entry.montant_effectif, Decimal('9999'))


class ForecastEntryApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM4 API', slug='taqinor-ntcrm4-api')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm4', password='x', company=self.company, role=self.role)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_categoriser_3_leads_categories_differentes_totaux_par_categorie(self):
        leads = [
            Lead.objects.create(
                company=self.company, nom=f'Lead {i}', owner=self.user,
                montant_estime=Decimal('10000')) for i in range(3)
        ]
        categories = ['commit', 'best_case', 'pipeline']
        for lead, cat in zip(leads, categories):
            resp = self.client_api.post('/api/django/crm/forecast-entries/', {
                'lead': lead.pk, 'categorie': cat,
            })
            self.assertEqual(resp.status_code, 201, resp.data)

        resp = self.client_api.get('/api/django/crm/forecast-entries/')
        self.assertEqual(resp.status_code, 200)
        totaux = resp.data['totaux_par_categorie']
        self.assertEqual(Decimal(str(totaux['commit'])), Decimal('10000'))
        self.assertEqual(Decimal(str(totaux['best_case'])), Decimal('10000'))
        self.assertEqual(Decimal(str(totaux['pipeline'])), Decimal('10000'))
