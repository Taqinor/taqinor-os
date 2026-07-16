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

    def test_low_stock_excludes_zero_threshold(self):
        """ERR57 — un produit à seuil_alerte=0 (aucun seuil) n'est PAS signalé
        bas stock, même à 0 en stock ; un produit avec seuil renseigné l'est."""
        # seuil 0 → ignoré, même à quantité 0.
        Produit.objects.create(
            company=self.company, nom='SansSeuil', sku='Z-0',
            prix_vente=Decimal('100'), quantite_stock=0, seuil_alerte=0)
        # seuil renseigné et stock sous le seuil → signalé.
        Produit.objects.create(
            company=self.company, nom='AvecSeuil', sku='Z-1',
            prix_vente=Decimal('100'), quantite_stock=2, seuil_alerte=5)
        resp = self.api.get('/api/django/reporting/reports/stock/')
        self.assertEqual(resp.status_code, 200)
        noms = {p['nom'] for p in resp.data['bas_stock']}
        self.assertIn('AvecSeuil', noms)
        self.assertNotIn('SansSeuil', noms)


class TestServiceReport(ReportsBase):
    def test_structure(self):
        resp = self.api.get('/api/django/reporting/reports/service/')
        self.assertEqual(resp.status_code, 200)
        for key in ('chantiers_par_statut', 'tickets_ouverts', 'tickets_resolus',
                    'garanties_expirantes_90j'):
            self.assertIn(key, resp.data)


class TestPeriodComparison(ReportsBase):
    """FG92 — comparaison MoM/YoY sur sales_report et dashboard."""

    def _create_old_lead(self, nom='OldLead'):
        from datetime import date, timedelta
        lead = Lead.objects.create(company=self.company, nom=nom, stage='NEW')
        # Décale la création dans le mois précédent pour la comparaison MoM.
        prev_date = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
        Lead.objects.filter(pk=lead.pk).update(date_creation=prev_date)
        return lead

    def test_compare_prev_sales_report(self):
        """?compare=prev retourne un bloc comparison avec current/previous/delta_pct."""
        Lead.objects.create(company=self.company, nom='CurrLead', stage='NEW')
        self._create_old_lead()
        resp = self.api.get('/api/django/reporting/reports/sales/?compare=prev')
        self.assertEqual(resp.status_code, 200)
        c = resp.data.get('comparison')
        self.assertIsNotNone(c, 'comparison manquante')
        self.assertEqual(c['period'], 'prev')
        self.assertIn('total_leads', c)
        self.assertIn('current', c['total_leads'])
        self.assertIn('previous', c['total_leads'])
        self.assertIn('delta_pct', c['total_leads'])

    def test_compare_yoy_sales_report(self):
        """?compare=yoy compare avec le même mois il y a un an."""
        Lead.objects.create(company=self.company, nom='ThisYear', stage='NEW')
        resp = self.api.get('/api/django/reporting/reports/sales/?compare=yoy')
        self.assertEqual(resp.status_code, 200)
        c = resp.data.get('comparison')
        self.assertIsNotNone(c)
        self.assertEqual(c['period'], 'yoy')

    def test_no_compare_returns_null(self):
        """Sans ?compare, comparison est None."""
        resp = self.api.get('/api/django/reporting/reports/sales/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data.get('comparison'))

    def test_compare_prev_dashboard(self):
        """?compare=prev sur le dashboard retourne un bloc comparison."""
        resp = self.api.get('/api/django/reporting/dashboard/?compare=prev')
        self.assertEqual(resp.status_code, 200)
        c = resp.data.get('comparison')
        self.assertIsNotNone(c)
        self.assertIn('ca_paye', c)
        self.assertIn('nb_leads', c)


class TestPDFExport(ReportsBase):
    """FG95 — ?export=pdf rend un PDF branded sans prix d'achat."""

    def _patch_weasyprint(self):
        """Remplace WeasyPrint par un stub retournant un PDF minimal valide."""
        import unittest.mock as mock
        # Stub PDF minimal (en-tête PDF).
        stub_pdf = b'%PDF-1.4 fake'

        patcher = mock.patch(
            'weasyprint.HTML',
            return_value=mock.MagicMock(write_pdf=mock.MagicMock(return_value=stub_pdf)),
        )
        return patcher

    def test_sales_export_pdf_returns_pdf_content_type(self):
        """?export=pdf sur le rapport ventes retourne application/pdf."""
        with self._patch_weasyprint():
            resp = self.api.get('/api/django/reporting/reports/sales/?export=pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('rapport-ventes.pdf', resp['Content-Disposition'])

    def test_stock_export_pdf_returns_pdf_content_type(self):
        """?export=pdf sur le rapport stock retourne application/pdf."""
        with self._patch_weasyprint():
            resp = self.api.get('/api/django/reporting/reports/stock/?export=pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_service_export_pdf_returns_pdf_content_type(self):
        """?export=pdf sur le rapport service retourne application/pdf."""
        with self._patch_weasyprint():
            resp = self.api.get('/api/django/reporting/reports/service/?export=pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_stock_pdf_does_not_contain_buy_price(self):
        """Le HTML généré pour le rapport stock n'expose jamais le prix d'achat."""
        from decimal import Decimal
        from apps.stock.models import Produit
        import unittest.mock as mock

        Produit.objects.create(
            company=self.company, nom='PanneauTest', sku='FG95-T',
            prix_vente=Decimal('5000'), prix_achat=Decimal('3000'),
            quantite_stock=2)

        captured_html = {}

        class FakeHTML:
            def __init__(self, string=None, **kw):
                captured_html['html'] = string

            def write_pdf(self, target=None):
                data = b'%PDF-1.4 fake'
                if target is not None:
                    target.write(data)
                    return None
                return data

        with mock.patch('weasyprint.HTML', FakeHTML):
            resp = self.api.get('/api/django/reporting/reports/stock/?export=pdf')

        self.assertEqual(resp.status_code, 200)
        html = captured_html.get('html', '')
        # prix_achat (3000) ne doit jamais apparaître dans la sortie PDF
        self.assertNotIn('3000', html,
                         'Le prix d\'achat est apparu dans le HTML du PDF stock')
