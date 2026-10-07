"""ASTK34 — `POST /stock/mouvements/` passe par `record_stock_movement`
(ajustement : niveau visé → écart signé, `quantite` = |écart|) et refuse les
types transfert et rebut sur cette route.

Rejoue MVT-5 de l'audit stock du 2026-10-06 : avant correction, depuis 100,
transfert q=5 → 201 et stock 5 ; rebut q=3 → 201 et stock 3 ; ajustement
q=−4 → 201 et stock −4 ; l'événement `mouvement_stock_enregistre` n'était
émis que par le service (0 via la vue).

Run:
    python manage.py test apps.stock.test_astk_mouvement_via_service -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import MouvementStock, Produit
from apps.stock.test_aud223_mouvement_service_unique import CaptureEvenements

User = get_user_model()

URL = '/api/django/stock/mouvements/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class MouvementViaServiceTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk34', slug='astk34')
        self.resp = User.objects.create_user(
            username='astk34-resp', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.resp)
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau ASTK34', sku='PAN-ASTK34',
            prix_vente=Decimal('100'), quantite_stock=100)

    def _post(self, type_mouvement, quantite):
        return self.api.post(URL, {
            'produit': self.produit.pk, 'type_mouvement': type_mouvement,
            'quantite': quantite}, format='json')

    def _stock(self):
        self.produit.refresh_from_db()
        return self.produit.quantite_stock

    def test_transfert_et_rebut_refuses(self):
        for type_mv, q in (('transfert', 5), ('rebut', 3)):
            r = self._post(type_mv, q)
            self.assertEqual(r.status_code, 400, r.content)
            self.assertIn('type_mouvement', r.json())
        self.assertEqual(self._stock(), 100)
        self.assertFalse(MouvementStock.objects.exists())

    def test_ajustement_negatif_refuse(self):
        r = self._post('ajustement', -4)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self._stock(), 100)
        self.assertFalse(MouvementStock.objects.exists())

    def test_ajustement_niveau_vers_ecart(self):
        r = self._post('ajustement', 80)
        self.assertEqual(r.status_code, 201, r.content)
        m = MouvementStock.objects.get(pk=r.json()['id'])
        self.assertEqual(m.type_mouvement,
                         MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual((m.quantite, m.quantite_avant, m.quantite_apres),
                         (20, 100, 80))
        self.assertEqual(r.json()['quantite'], 20)
        self.assertEqual(self._stock(), 80)

    def test_evenement_emis(self):
        with CaptureEvenements() as capture:
            r1 = self._post('ajustement', 80)
            r2 = self._post('entree', 10)
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(len(capture), 2)
        entree = MouvementStock.objects.get(pk=r2.json()['id'])
        self.assertEqual((entree.quantite, entree.quantite_avant,
                          entree.quantite_apres), (10, 80, 90))
        # Stock relu = dernier quantite_apres du registre.
        dernier = MouvementStock.objects.filter(
            produit=self.produit).order_by('-date', '-id').first()
        self.assertEqual(self._stock(), 90)
        self.assertEqual(dernier.quantite_apres, 90)
        self.assertEqual(entree.company_id, self.co.pk)
        self.assertEqual(entree.created_by_id, self.resp.pk)
