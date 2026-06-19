"""T12 — export comptable journal des ventes + résumé TVA."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.exports import period_bounds
from authentication.models import Company

User = get_user_model()


class TestPeriodBounds(TestCase):
    def test_month(self):
        d, f = period_bounds({'month': '2026-06'})
        self.assertEqual((d, f), (date(2026, 6, 1), date(2026, 7, 1)))

    def test_quarter(self):
        d, f = period_bounds({'quarter': '2026-Q2'})
        self.assertEqual((d, f), (date(2026, 4, 1), date(2026, 7, 1)))


class TestJournalExport(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='jr-co', defaults={'nom': 'JR Co'})[0]
        self.user = User.objects.create_user(
            username='jr_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        c = Client.objects.create(company=self.company, nom='C', ice='000111222')
        p = Produit.objects.create(company=self.company, nom='Panneau', sku='J-1',
                                   prix_vente=Decimal('1000'), quantite_stock=5)
        fac = Facture.objects.create(
            company=self.company, reference='FAC-JR-1', client=c, statut='emise',
            taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=fac, produit=p, designation='Panneaux', quantite=Decimal('10'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('10'))
        LigneFacture.objects.create(
            facture=fac, produit=p, designation='Pose', quantite=Decimal('1'),
            prix_unitaire=Decimal('2000'), remise=Decimal('0'), taux_tva=Decimal('20'))

    def test_export_returns_xlsx(self):
        resp = self.api.get('/api/django/ventes/journal-ventes/?month=%s'
                            % date.today().strftime('%Y-%m'))
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))
        self.assertGreater(len(body), 2000)

    def _load_journal_rows(self):
        from datetime import date as _date
        from apps.ventes.exports import export_journal_ventes, period_bounds
        from openpyxl import load_workbook
        from io import BytesIO
        debut, fin = period_bounds({'month': _date.today().strftime('%Y-%m')})
        resp = export_journal_ventes(self.company, debut, fin)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        wb = load_workbook(BytesIO(body))
        ws = wb['Journal des ventes']
        return [list(r) for r in ws.iter_rows(values_only=True)]

    def test_type_column_present(self):
        rows = self._load_journal_rows()
        self.assertEqual(rows[0][2], 'Type')
        # Les factures classiques (chaîne BC) sont de type « Facture complète ».
        self.assertEqual(rows[1][2], 'Facture complète')

    def test_avoirs_appear_as_negative_lines(self):
        from apps.ventes.models import Avoir, LigneAvoir
        from apps.crm.models import Client
        fac = Facture.objects.get(reference='FAC-JR-1')
        avoir = Avoir.objects.create(
            company=self.company, reference='AVO-JR-1', facture=fac,
            client=Client.objects.get(nom='C'), statut='emise',
            taux_tva=Decimal('20'))
        LigneAvoir.objects.create(
            avoir=avoir, designation='Retour', quantite=Decimal('1'),
            prix_unitaire=Decimal('2000'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        rows = self._load_journal_rows()
        avoir_rows = [r for r in rows if r[2] == 'Avoir']
        self.assertEqual(len(avoir_rows), 1)
        # Total HT (col index 8) et Total TTC (col index 11) sont négatifs.
        self.assertLess(avoir_rows[0][8], 0)
        self.assertLess(avoir_rows[0][11], 0)

    def test_export_comptable_xlsx(self):
        from datetime import timedelta
        d = date.today()
        start = d.strftime('%Y-%m-01')
        end = (d + timedelta(days=1)).strftime('%Y-%m-%d')
        resp = self.api.get(
            f'/api/django/ventes/export-comptable/?start={start}&end={end}'
            f'&format=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = (b''.join(resp.streaming_content)
                if resp.streaming else resp.content)
        self.assertTrue(body.startswith(b'PK'))
        # Le contenu contient l'ICE client + une ligne TOTAL.
        from openpyxl import load_workbook
        from io import BytesIO
        ws = load_workbook(BytesIO(body)).active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        self.assertEqual(rows[0][4], 'ICE client')
        self.assertIn('000111222', [r[4] for r in rows[1:] if r[4]])
        self.assertTrue(any(r[0] == 'TOTAL' for r in rows))

    def test_export_comptable_csv(self):
        from datetime import timedelta
        d = date.today()
        start = d.strftime('%Y-%m-01')
        end = (d + timedelta(days=1)).strftime('%Y-%m-%d')
        resp = self.api.get(
            f'/api/django/ventes/export-comptable/?start={start}&end={end}'
            f'&format=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        text = resp.content.decode('utf-8')
        self.assertIn('ICE client', text)
        self.assertIn('000111222', text)
        self.assertIn('TOTAL', text)

    def test_export_comptable_excludes_brouillon(self):
        # Une facture brouillon ne doit jamais apparaître dans l'export.
        from apps.crm.models import Client
        Facture.objects.create(
            company=self.company, reference='FAC-JR-DRAFT',
            client=Client.objects.get(nom='C'), statut='brouillon',
            taux_tva=Decimal('20'))
        from datetime import timedelta
        d = date.today()
        start = d.strftime('%Y-%m-01')
        end = (d + timedelta(days=1)).strftime('%Y-%m-%d')
        resp = self.api.get(
            f'/api/django/ventes/export-comptable/?start={start}&end={end}'
            f'&format=csv')
        self.assertNotIn('FAC-JR-DRAFT', resp.content.decode('utf-8'))
