"""ASTK28 — le registre des mouvements de stock est APPEND-ONLY par l'API
REST (PUT/PATCH/DELETE → 405), comme l'admin depuis AUD215.

Rejoue MVT-6 de l'audit stock du 2026-10-06 : avant correction, un admin
PATCH {quantite: 999} → 200 et DELETE → 204 (mouvement effacé, valorisation
à date d'une date antérieure faussée).

Run:
    python manage.py test apps.stock.test_astk_registre_append_only -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import record_stock_movement

User = get_user_model()

URL = '/api/django/stock/mouvements/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RegistreAppendOnlyTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk28', slug='astk28')
        self.admin = User.objects.create_user(
            username='astk28-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.admin)
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau ASTK28', sku='PAN-ASTK28',
            prix_vente=Decimal('100'), quantite_stock=0)
        self.m = record_stock_movement(
            company=self.co, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE, quantite=12,
            quantite_avant=0, quantite_apres=12, reference='REC-ASTK28',
            note='Réception', created_by=self.admin)

    def test_patch_put_delete_refuses(self):
        url = f'{URL}{self.m.pk}/'
        r = self.api.patch(url, {'quantite': 999}, format='json')
        self.assertEqual(r.status_code, 405, r.content)
        r = self.api.put(url, {
            'produit': self.produit.pk, 'type_mouvement': 'entree',
            'quantite': 999}, format='json')
        self.assertEqual(r.status_code, 405, r.content)
        r = self.api.delete(url)
        self.assertEqual(r.status_code, 405, r.content)

        self.m.refresh_from_db()
        self.assertEqual(self.m.quantite, 12)
        self.assertEqual(self.m.quantite_apres, 12)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 12)

    def test_lecture_et_creation_restent_ouvertes(self):
        self.assertEqual(self.api.get(URL).status_code, 200)
        self.assertEqual(self.api.get(f'{URL}{self.m.pk}/').status_code, 200)
        r = self.api.post(URL, {
            'produit': self.produit.pk, 'type_mouvement': 'entree',
            'quantite': 3}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
