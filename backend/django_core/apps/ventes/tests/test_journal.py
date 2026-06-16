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
