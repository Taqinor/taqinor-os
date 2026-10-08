"""ASTK209 (C-ASTK-053, MVT-22) — l'inventaire physique refuse toute quantité
comptée non entière ou négative, en nommant chaque ligne, sans rien appliquer.

Sonde MVT-22 rejouée : trois produits à 20, POST produits/inventaire/ avec
7.5 (float), "7.5" (texte) et -3 → AVANT : stock A tronqué à 7, B et C
ignorés en silence, réponse {ajustes: 1} sans erreur. APRÈS : 400
{lignes: {"0": [...], "1": [...], "2": [...]}} et les trois produits restent
à 20 (validation de toutes les lignes avant toute écriture).

Run :
    python manage.py test apps.stock.test_astk_inventaire_saisie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.stock.models import MouvementStock, Produit

User = get_user_model()
URL = '/api/django/stock/produits/inventaire/'
MESSAGE = ['Quantité entière ≥ 0 attendue.']


class InventaireSaisieTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='astk209', slug='astk209')
        self.admin = User.objects.create_user(
            username='astk209-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.a, self.b, self.c = (
            Produit.objects.create(
                company=self.company, nom=f'Produit {n}', sku=f'ASTK209-{n}',
                prix_achat=Decimal('10'), prix_vente=Decimal('20'),
                quantite_stock=20)
            for n in 'ABC')

    def _poster(self, lignes):
        return self.api.post(URL, {'motif': 'test', 'lignes': lignes},
                             format='json')

    def _stocks(self):
        return [Produit.objects.get(pk=p.pk).quantite_stock
                for p in (self.a, self.b, self.c)]

    def test_decimal_refuse_400(self):
        resp = self._poster([{'produit': self.a.id, 'quantite_comptee': 7.5}])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['lignes'], {'0': MESSAGE})
        self.assertEqual(self._stocks(), [20, 20, 20])

    def test_chaine_decimale_refusee(self):
        resp = self._poster([{'produit': self.b.id, 'quantite_comptee': '7.5'}])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['lignes'], {'0': MESSAGE})

    def test_negatif_refuse(self):
        resp = self._poster([{'produit': self.c.id, 'quantite_comptee': -3}])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['lignes'], {'0': MESSAGE})

    def test_rien_applique_si_une_ligne_invalide(self):
        resp = self._poster([
            {'produit': self.a.id, 'quantite_comptee': 7.5},
            {'produit': self.b.id, 'quantite_comptee': '7.5'},
            {'produit': self.c.id, 'quantite_comptee': -3},
        ])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['lignes'],
                         {'0': MESSAGE, '1': MESSAGE, '2': MESSAGE})
        self.assertEqual(self._stocks(), [20, 20, 20])
        # Une ligne valide accompagnée d'une invalide n'est pas appliquée non plus.
        resp = self._poster([
            {'produit': self.a.id, 'quantite_comptee': 7},
            {'produit': self.b.id, 'quantite_comptee': 'abc'},
        ])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['lignes'], {'1': MESSAGE})
        self.assertEqual(self._stocks(), [20, 20, 20])
        self.assertFalse(MouvementStock.objects.filter(
            reference='INVENTAIRE', produit__company=self.company).exists())

    def test_saisie_valide_ajuste_comme_avant(self):
        resp = self._poster([
            {'produit': self.a.id, 'quantite_comptee': 7},
            {'produit': self.b.id, 'quantite_comptee': '20'},
            {'produit': self.c.id, 'quantite_comptee': 0},
        ])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['ajustes'], 2)
        self.assertEqual(resp.json()['inchanges'], 1)
        self.assertEqual(self._stocks(), [7, 20, 0])
