"""NTFSM19 — Réappro automatique van-stock (étend FG62).

Critère d'acceptation testé : cliquer « Créer transfert » sur une
camionnette sous son seuil crée un `TransfertStock` avec les bonnes
quantités, sans dupliquer si déjà en attente.

Run :
    python manage.py test apps.stock.test_ntfsm19_van_stock_reappro -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, Produit, StockEmplacement, TransfertStock,
)
from apps.stock.selectors import van_stock_a_reapprovisionner

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username):
    user, _ = User.objects.get_or_create(
        username=username, defaults={'company': company, 'role_legacy': 'admin'})
    return user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestVanStockAReapprovisionner(TestCase):
    def setUp(self):
        self.company = make_company('ntfsm19-co', 'NTFSM19 Co')
        self.admin = make_admin(self.company, 'ntfsm19_admin')
        self.api = auth(self.admin)
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.van = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 1', is_principal=False)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W',
            prix_vente=Decimal('900'), prix_achat=Decimal('600'),
            quantite_stock=20, seuil_alerte=3)
        self.se = StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.van, quantite=2, seuil_min=5, seuil_max=10)

    def test_selector_delegates_to_fg62_calculation(self):
        result = van_stock_a_reapprovisionner(self.company)
        item = next(
            (d for d in result if d['emplacement_id'] == self.van.id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item['produit_id'], self.produit.id)
        self.assertEqual(item['qte_suggere_transfert'], 3)

    def test_endpoint_lists_ecart(self):
        r = self.api.get(
            '/api/django/stock/emplacements/van-stock/a-reapprovisionner/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(any(d['emplacement_id'] == self.van.id for d in data))

    def test_creer_transfert_cree_demande_avec_bonnes_quantites(self):
        r = self.api.post(
            '/api/django/stock/emplacements/van-stock/creer-transfert/',
            {'produit_id': self.produit.id, 'emplacement_id': self.van.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['quantite'], 3)
        self.assertEqual(r.data['statut'], TransfertStock.Statut.DEMANDE)
        self.assertEqual(r.data['source'], self.principal.id)
        self.assertEqual(r.data['destination'], self.van.id)
        self.assertEqual(TransfertStock.objects.count(), 1)

    def test_creer_transfert_ne_duplique_pas_si_deja_en_attente(self):
        r1 = self.api.post(
            '/api/django/stock/emplacements/van-stock/creer-transfert/',
            {'produit_id': self.produit.id, 'emplacement_id': self.van.id},
            format='json')
        self.assertEqual(r1.status_code, 201)
        r2 = self.api.post(
            '/api/django/stock/emplacements/van-stock/creer-transfert/',
            {'produit_id': self.produit.id, 'emplacement_id': self.van.id},
            format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['id'], r1.data['id'])
        self.assertEqual(TransfertStock.objects.count(), 1)

    def test_creer_transfert_sans_ecart_refuse(self):
        # Stock déjà au seuil max : plus d'écart sous seuil.
        self.se.quantite = 10
        self.se.save(update_fields=['quantite'])
        r = self.api.post(
            '/api/django/stock/emplacements/van-stock/creer-transfert/',
            {'produit_id': self.produit.id, 'emplacement_id': self.van.id},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_creer_transfert_champs_requis(self):
        r = self.api.post(
            '/api/django/stock/emplacements/van-stock/creer-transfert/',
            {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_isolation_societe(self):
        company2 = make_company('ntfsm19-co2', 'NTFSM19 Co 2')
        result = van_stock_a_reapprovisionner(company2)
        ids = [d['produit_id'] for d in result]
        self.assertNotIn(self.produit.id, ids)
