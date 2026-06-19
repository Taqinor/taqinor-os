"""T13/T14/T15 — hub Rapports (ventes, stock, service) + export xlsx."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class ReportsBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='rep-co', defaults={'nom': 'Rep Co'})[0]
        self.user = User.objects.create_user(
            username='rep_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestSalesReport(ReportsBase):
    def test_funnel_and_xlsx(self):
        Lead.objects.create(company=self.company, nom='A', stage='NEW')
        Lead.objects.create(company=self.company, nom='B', stage='SIGNED')
        resp = self.api.get('/api/django/reporting/reports/sales/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_leads'], 2)
        self.assertEqual(len(resp.data['funnel']), 6)
        self.assertIn('devis_par_statut', resp.data)
        x = self.api.get('/api/django/reporting/reports/sales/?export=xlsx')
        body = b''.join(x.streaming_content) if x.streaming else x.content
        self.assertTrue(body.startswith(b'PK'))

    def test_devis_par_statut_includes_expire_bucket(self):
        """Un devis envoyé dont la validité est dépassée tombe sous « Expiré »."""
        from datetime import date, timedelta
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        client = Client.objects.create(company=self.company, nom='CliDev')
        Devis.objects.create(
            company=self.company, reference='DEV-EXP-1', client=client,
            statut=Devis.Statut.ENVOYE,
            date_validite=date.today() - timedelta(days=5))
        resp = self.api.get('/api/django/reporting/reports/sales/')
        self.assertEqual(resp.status_code, 200)
        statuts = {d['statut'] for d in resp.data['devis_par_statut']}
        self.assertIn('expire', statuts)

    def test_period_filter_limits_leads(self):
        """?from=&to= borne le funnel aux leads créés dans la fenêtre."""
        from datetime import date, timedelta
        old = Lead.objects.create(company=self.company, nom='Old', stage='NEW')
        Lead.objects.filter(pk=old.pk).update(
            date_creation=date.today() - timedelta(days=400))
        Lead.objects.create(company=self.company, nom='Recent', stage='NEW')
        today = date.today().isoformat()
        recent = (date.today() - timedelta(days=7)).isoformat()
        resp = self.api.get(
            f'/api/django/reporting/reports/sales/?from={recent}&to={today}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_leads'], 1)


class TestStockReport(ReportsBase):
    def test_valuation_includes_internal_buy(self):
        Produit.objects.create(company=self.company, nom='P', sku='R-1',
                               prix_vente=Decimal('1000'), prix_achat=Decimal('600'),
                               quantite_stock=10)
        resp = self.api.get('/api/django/reporting/reports/stock/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['valorisation_vente'], '10000.00')
        self.assertEqual(resp.data['valorisation_achat'], '6000.00')


class TestServiceReport(ReportsBase):
    def test_structure(self):
        resp = self.api.get('/api/django/reporting/reports/service/')
        self.assertEqual(resp.status_code, 200)
        for key in ('chantiers_par_statut', 'tickets_ouverts', 'tickets_resolus',
                    'garanties_expirantes_90j'):
            self.assertIn(key, resp.data)
