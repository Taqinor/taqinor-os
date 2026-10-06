"""ASTK29 — une session d'inventaire VALIDÉE ou ANNULÉE est figée : PATCH/PUT
de ses lignes → 400 « session … : non modifiable » ; une session en cours
reste modifiable.

Rejoue MVT-20 de l'audit stock du 2026-10-06 : avant correction, PATCH
{lignes: []} d'une session validée → 200 et ses lignes disparaissaient alors
que l'ajustement posté restait au registre, orphelin.

Run:
    python manage.py test apps.stock.test_astk_inventaire_fige -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import InventaireSession, MouvementStock, Produit

User = get_user_model()

URL = '/api/django/stock/inventaire-sessions/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class InventaireFigeTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk29', slug='astk29')
        self.admin = User.objects.create_user(
            username='astk29-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.admin)
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble ASTK29', sku='CAB-ASTK29',
            prix_vente=Decimal('10'), quantite_stock=10)

    def _session(self):
        r = self.api.post(URL, {'motif': 'comptage', 'lignes': [{
            'produit': self.produit.pk, 'quantite_theorique': 10,
            'quantite_comptee': 8}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return InventaireSession.objects.get(pk=r.json()['id'])

    def test_patch_session_validee_refuse(self):
        session = self._session()
        r = self.api.post(f'{URL}{session.pk}/valider/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['ajustes'], 1)

        r = self.api.patch(f'{URL}{session.pk}/', {'lignes': []},
                           format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('non modifiable', r.json()['detail'])
        r = self.api.put(f'{URL}{session.pk}/',
                         {'motif': 'autre', 'lignes': []}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

        session.refresh_from_db()
        self.assertEqual(session.statut, InventaireSession.Statut.VALIDE)
        self.assertEqual(session.motif, 'comptage')
        self.assertEqual(session.lignes.count(), 1)
        # L'ajustement posté correspond toujours à une ligne de la session.
        ajustement = MouvementStock.objects.get(
            reference=session.reference,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT)
        ligne = session.lignes.get()
        self.assertEqual(ajustement.produit_id, ligne.produit_id)
        self.assertEqual(ajustement.quantite, 2)

    def test_patch_session_annulee_refuse(self):
        session = self._session()
        r = self.api.post(f'{URL}{session.pk}/annuler/')
        self.assertEqual(r.status_code, 200, r.content)
        r = self.api.patch(f'{URL}{session.pk}/', {'lignes': []},
                           format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(session.lignes.count(), 1)

    def test_session_en_cours_reste_modifiable(self):
        session = self._session()
        r = self.api.patch(f'{URL}{session.pk}/', {'lignes': [{
            'produit': self.produit.pk, 'quantite_theorique': 10,
            'quantite_comptee': 9}]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(session.lignes.get().quantite_comptee, 9)
