"""Tests stock multi-emplacements (N15).

Couvre :
  - amorçage idempotent du dépôt principal + camionnette ;
  - ventilation : tout le stock existant est au dépôt principal par défaut ;
  - transfert principal → camionnette (et retour) sans changer le total ;
  - refus d'un transfert supérieur au stock de la source / source == destination ;
  - scoping société (pas de transfert d'un produit d'une autre société) ;
  - emplacement détenant du stock non supprimable ; principal protégé.

Run :
    python manage.py test apps.stock.test_emplacements -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Produit, EmplacementStock, StockEmplacement, TransfertStock,
)
from apps.stock.services import (
    ensure_emplacements, stock_breakdown, transfer_stock,
)

User = get_user_model()


def make_company(slug='emp-co', nom='Emp Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EmplacementBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='emp_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN550',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=10)
        self.api = auth(self.admin)


class TestSeedAndBreakdown(EmplacementBase):
    def test_ensure_emplacements_idempotent(self):
        ensure_emplacements(self.company)
        ensure_emplacements(self.company)
        emps = EmplacementStock.objects.filter(company=self.company)
        self.assertEqual(emps.count(), 2)
        self.assertEqual(emps.filter(is_principal=True).count(), 1)
        self.assertTrue(emps.filter(nom='Camionnette').exists())

    def test_existing_stock_defaults_to_principal(self):
        breakdown = stock_breakdown(self.produit)
        by_name = {b['emplacement_nom']: b['quantite'] for b in breakdown}
        self.assertEqual(by_name['Dépôt principal'], 10)
        self.assertEqual(by_name['Camionnette'], 0)
        self.assertEqual(sum(b['quantite'] for b in breakdown), 10)


class TestTransfer(EmplacementBase):
    def _emps(self):
        ensure_emplacements(self.company)
        principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')
        return principal, camionnette

    def test_transfer_moves_qty_without_changing_total(self):
        principal, camionnette = self._emps()
        transfer_stock(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            source_id=principal.id, destination_id=camionnette.id, quantite=3)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)  # total inchangé
        by_name = {b['emplacement_nom']: b['quantite']
                   for b in stock_breakdown(self.produit)}
        self.assertEqual(by_name['Dépôt principal'], 7)
        self.assertEqual(by_name['Camionnette'], 3)
        self.assertTrue(TransfertStock.objects.filter(
            produit=self.produit, quantite=3).exists())

    def test_transfer_back_to_principal(self):
        principal, camionnette = self._emps()
        transfer_stock(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            source_id=principal.id, destination_id=camionnette.id, quantite=4)
        transfer_stock(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            source_id=camionnette.id, destination_id=principal.id, quantite=4)
        by_name = {b['emplacement_nom']: b['quantite']
                   for b in stock_breakdown(self.produit)}
        self.assertEqual(by_name['Dépôt principal'], 10)
        self.assertEqual(by_name['Camionnette'], 0)

    def test_reject_more_than_available(self):
        principal, camionnette = self._emps()
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=camionnette.id,
                destination_id=principal.id, quantite=1)  # camionnette vide

    def test_reject_same_source_destination(self):
        principal, _ = self._emps()
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=principal.id,
                destination_id=principal.id, quantite=1)

    def test_cross_tenant_blocked(self):
        other = make_company(slug='other-co', nom='Other Co')
        ensure_emplacements(other)
        principal, camionnette = self._emps()
        # produit appartient à self.company ; on l'attaque depuis other.
        with self.assertRaises(ValueError):
            transfer_stock(
                company=other, user=self.admin, produit_id=self.produit.id,
                source_id=principal.id, destination_id=camionnette.id,
                quantite=1)


class TestEmplacementApi(EmplacementBase):
    def test_list_autoseeds(self):
        r = self.api.get('/api/django/stock/emplacements/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data)
        noms = {e['nom'] for e in results}
        self.assertIn('Dépôt principal', noms)
        self.assertIn('Camionnette', noms)

    def test_produit_breakdown_endpoint(self):
        r = self.api.get(
            f'/api/django/stock/produits/{self.produit.id}/emplacements/')
        self.assertEqual(r.status_code, 200)
        total = sum(b['quantite'] for b in r.json())
        self.assertEqual(total, 10)

    def test_transfert_endpoint(self):
        ensure_emplacements(self.company)
        principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')
        r = self.api.post('/api/django/stock/transferts/', {
            'produit': self.produit.id, 'source': principal.id,
            'destination': camionnette.id, 'quantite': 2,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=camionnette)
        self.assertEqual(se.quantite, 2)

    def test_principal_not_deletable(self):
        ensure_emplacements(self.company)
        principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        r = self.api.delete(
            f'/api/django/stock/emplacements/{principal.id}/')
        self.assertEqual(r.status_code, 400)

    def test_emplacement_holding_stock_not_deletable(self):
        ensure_emplacements(self.company)
        principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')
        transfer_stock(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            source_id=principal.id, destination_id=camionnette.id, quantite=1)
        r = self.api.delete(
            f'/api/django/stock/emplacements/{camionnette.id}/')
        self.assertEqual(r.status_code, 409)
