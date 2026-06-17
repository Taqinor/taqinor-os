"""N46 (pièces consommées → stock) + N47 (renouvellement + rapport PDF)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.sav.models import Ticket, PieceConsommee, ContratMaintenance

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestSavPieces(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='piece-co', defaults={'nom': 'Piece Co'})[0]
        self.user = User.objects.create_user(
            username='piece_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-P-1', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Carte', sku='CRT-1',
            prix_vente=Decimal('200'), quantite_stock=Decimal('10'))

    def _add(self, **body):
        return self.api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/',
            {'produit': self.produit.id, **body}, format='json')

    def test_add_piece_without_decrement_keeps_stock(self):
        r = self._add(quantite='2')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['stock_decremente'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('10'))

    def test_add_piece_with_decrement_reduces_stock(self):
        r = self._add(quantite='3', decrement=True)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['stock_decremente'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('7'))

    def test_remove_decremented_piece_restores_stock(self):
        r = self._add(quantite='3', decrement=True)
        pid = r.data['id']
        d = self.api.delete(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/{pid}/')
        self.assertEqual(d.status_code, 204)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('10'))
        self.assertFalse(PieceConsommee.objects.filter(id=pid).exists())

    def test_pieces_listed_with_designation(self):
        self._add(quantite='1')
        r = self.api.get(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['produit_nom'], 'Carte')
        # Aucun prix d'achat exposé.
        self.assertNotIn('prix_achat', r.data[0])


class TestMaintenanceRenewal(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='maint-co', defaults={'nom': 'Maint Co'})[0]
        self.user = User.objects.create_user(
            username='maint_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C')

    def test_renouvellement_du_flag(self):
        past = date.today() - timedelta(days=1)
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date.today(),
            date_renouvellement=past, actif=True)
        self.assertTrue(contrat.renouvellement_du())

    def test_renouvellement_not_due_without_date(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date.today(), actif=True)
        self.assertFalse(contrat.renouvellement_du())

    def test_rapport_pdf(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date.today(), actif=True)
        r = self.api.get(
            '/api/django/sav/contrats-maintenance/'
            f'{contrat.id}/rapport-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
