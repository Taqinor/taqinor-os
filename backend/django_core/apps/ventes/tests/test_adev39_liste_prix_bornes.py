"""ADEV39 (C-ADEV-056) — ``POST /ventes/listes-prix/<id>/lignes/`` valide le
prix par un sérialiseur : NaN, négatif ou hors plage → 400 nommant
``prix_unitaire`` (plus jamais un 500 ni un prix négatif servi) ; la borne
haute du modèle (99 999 999,99) passe.

Rejoue VC p6. Test-du-test : retirer ``min_value=0`` ⇒ le cas -5 échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.stock.models import Produit
from apps.ventes.models import LignePrixListe, ListePrix
from authentication.models import Company

User = get_user_model()


class ListePrixBornesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADEV39', slug='adev39-co')
        self.user = User.objects.create_user(
            username='adev39_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.liste = ListePrix.objects.create(
            company=self.company, nom='Revendeurs')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='ADEV39-OND',
            prix_vente=Decimal('10000'), quantite_stock=1)
        self.url = '/api/django/ventes/listes-prix/%s/lignes/' % self.liste.pk

    def _post(self, prix):
        return self.api.post(self.url, {'produit': self.produit.pk,
                                        'prix_unitaire': prix}, format='json')

    def test_valeurs_refusees_400_sans_ligne(self):
        for prix in ('NaN', '-5', '1e12'):
            with self.subTest(prix=prix):
                resp = self._post(prix)
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertIn('prix_unitaire', resp.json())
                # CLAUSE PERSISTANCE — aucune ligne créée.
                self.assertFalse(LignePrixListe.objects.filter(
                    liste=self.liste).exists())

    def test_borne_haute_acceptee(self):
        resp = self._post('99999999.99')
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne = LignePrixListe.objects.get(liste=self.liste)
        self.assertEqual(ligne.prix_unitaire, Decimal('99999999.99'))
