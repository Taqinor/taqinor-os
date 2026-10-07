"""ASTK32 — `quantite_stock` non inscriptible par l'API produit en
modification ; une quantité initiale à la création devient un mouvement
ENTREE « stock initial » posé par `record_stock_movement`.

Rejoue CAT-2 (PATCH quantite_stock=3 sur 10 → 200, stock 3, aucun
mouvement) et MVT-3 (PATCH {prix_vente, quantite_stock: 10} d'un formulaire
ouvert avant une réception +5 → stock 10 alors que le registre dit 15) de
l'audit stock du 2026-10-06.

Run:
    python manage.py test apps.stock.test_astk_quantite_stock_ro -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import record_stock_movement

User = get_user_model()

URL = '/api/django/stock/produits/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class QuantiteStockLectureSeuleTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk32', slug='astk32')
        self.admin = User.objects.create_user(
            username='astk32-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.admin)
        # QG4 — la CRÉATION de produit est réservée au Directeur (et au
        # Commercial responsable) : les POST passent par un Directeur réel.
        perms = dict(CANONICAL_SYSTEM_ROLES)['Directeur']
        directeur = User.objects.create_user(
            username='astk32-directeur', password='x', company=self.co,
            role=Role.objects.create(
                company=self.co, nom='Directeur', permissions=list(perms),
                est_systeme=True))
        self.api_creation = _api(directeur)
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur ASTK32', sku='OND-ASTK32',
            prix_vente=Decimal('50'), quantite_stock=10)
        # Réception +5 par le service réel : stock 15, registre 15.
        record_stock_movement(
            company=self.co, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE, quantite=5,
            quantite_avant=10, quantite_apres=15, reference='REC-ASTK32',
            note='Réception', created_by=self.admin)

    def _dernier_apres(self, produit):
        return (MouvementStock.objects.filter(produit=produit)
                .order_by('-date', '-id').values_list(
                    'quantite_apres', flat=True).first())

    def test_patch_ignore_quantite(self):
        url = f'{URL}{self.produit.pk}/'
        r = self.api.patch(url, {'prix_vente': '99', 'quantite_stock': 10},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['quantite_stock'], 15)
        r = self.api.patch(url, {'quantite_stock': 3}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 15)
        self.assertEqual(self.produit.prix_vente, Decimal('99'))
        self.assertEqual(self._dernier_apres(self.produit), 15)
        self.assertEqual(
            MouvementStock.objects.filter(produit=self.produit).count(), 1)

    def test_creation_pose_mouvement_initial(self):
        r = self.api_creation.post(URL, {
            'nom': 'Batterie ASTK32', 'sku': 'BAT-ASTK32',
            'prix_vente': '120', 'quantite_stock': 7,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        produit = Produit.objects.get(pk=r.json()['id'])
        self.assertEqual(produit.quantite_stock, 7)
        mouvements = MouvementStock.objects.filter(produit=produit)
        self.assertEqual(mouvements.count(), 1)
        m = mouvements.get()
        self.assertEqual(m.type_mouvement,
                         MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual((m.quantite, m.quantite_avant, m.quantite_apres),
                         (7, 0, 7))
        self.assertEqual(m.reference, 'Stock initial')
        self.assertEqual(m.company_id, self.co.pk)
        self.assertEqual(self._dernier_apres(produit), produit.quantite_stock)

    def test_creation_sans_quantite_aucun_mouvement(self):
        r = self.api_creation.post(URL, {
            'nom': 'Câble ASTK32', 'sku': 'CAB-ASTK32', 'prix_vente': '5',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        produit = Produit.objects.get(pk=r.json()['id'])
        self.assertEqual(produit.quantite_stock, 0)
        self.assertFalse(MouvementStock.objects.filter(
            produit=produit).exists())

    def test_creation_quantite_negative_refusee(self):
        r = self.api_creation.post(URL, {
            'nom': 'Neg ASTK32', 'sku': 'NEG-ASTK32', 'prix_vente': '5',
            'quantite_stock': -2,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('quantite_stock', r.json())
        self.assertFalse(Produit.objects.filter(sku='NEG-ASTK32').exists())
