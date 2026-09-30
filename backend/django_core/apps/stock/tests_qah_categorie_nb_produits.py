"""Régression ERR-QAH-STOCK-CATEGORIES-COMPTE-ZERO.

`/stock/categories` affichait « PRODUITS : 0 » sur toutes les catégories :
`GET /api/django/stock/categories/` ne renvoyait aucun champ de comptage.
L'API expose désormais `nb_produits` (produits NON archivés, scopé société).

Run:
    python manage.py test apps.stock.tests_qah_categorie_nb_produits -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie, Produit

User = get_user_model()


def _company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestCategorieNbProduits(TestCase):
    def setUp(self):
        self.company = _company('qah-catnb-co', 'QAH CatNb Co')
        self.user, _ = User.objects.get_or_create(
            username='admin_qah_catnb',
            defaults={'company': self.company, 'role_legacy': 'admin'})
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.cat = Categorie.objects.create(company=self.company, nom='Panneaux')
        self.vide = Categorie.objects.create(company=self.company, nom='Vide')
        for i in range(3):
            Produit.objects.create(
                company=self.company, nom=f'Panneau {i}', categorie=self.cat,
                prix_vente=Decimal('100'))
        Produit.objects.create(
            company=self.company, nom='Panneau archivé', categorie=self.cat,
            prix_vente=Decimal('100'), is_archived=True)

    def _rows(self, data):
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        return data

    def test_liste_expose_nb_produits_non_archives(self):
        r = self.client.get('/api/django/stock/categories/')
        self.assertEqual(r.status_code, 200, r.content)
        by_id = {row['id']: row for row in self._rows(r.data)}
        self.assertEqual(by_id[self.cat.id]['nb_produits'], 3)
        self.assertEqual(by_id[self.vide.id]['nb_produits'], 0)

    def test_detail_expose_nb_produits(self):
        r = self.client.get(f'/api/django/stock/categories/{self.cat.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['nb_produits'], 3)

    def test_nb_produits_est_lecture_seule(self):
        r = self.client.patch(
            f'/api/django/stock/categories/{self.cat.id}/',
            {'nb_produits': 99}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['nb_produits'], 3)
