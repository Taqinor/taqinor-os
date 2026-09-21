"""NTHOT13 — Cartes/menus avec recettes et fiches techniques.

Done = une recette liste ses ingrédients avec quantités et ses allergènes
déclarés, tests.
"""
from decimal import Decimal

from django.test import TestCase

from apps.hospitality.models import IngredientRecette, Recette

from .helpers import auth, make_company, make_user


class RecetteApiTests(TestCase):
    def setUp(self):
        from apps.stock.models import Produit

        self.co = make_company('hot-rec', 'Hôtel')
        self.resp = make_user(self.co, 'hot-rec-resp', role='responsable')
        self.normal = make_user(self.co, 'hot-rec-normal', role='normal')
        self.farine = Produit.objects.create(
            company=self.co, nom='Farine', prix_achat=Decimal('5'),
            prix_vente=Decimal('8'))
        self.beurre = Produit.objects.create(
            company=self.co, nom='Beurre', prix_achat=Decimal('20'),
            prix_vente=Decimal('30'))

    def test_creer_recette_avec_allergenes(self):
        resp = auth(self.resp).post(
            '/api/django/hospitality/recettes/',
            {
                'nom_plat': 'Tarte au beurre', 'categorie_menu': 'dessert',
                'prix_vente_ht': '45.00',
                'allergenes': ['gluten', 'lactose'],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['allergenes'], ['gluten', 'lactose'])

    def test_ajouter_et_lister_ingredients_avec_quantites(self):
        recette = Recette.objects.create(
            company=self.co, nom_plat='Tarte', prix_vente_ht=Decimal('45'))
        resp = auth(self.resp).post(
            f'/api/django/hospitality/recettes/{recette.pk}/ingredients/',
            {'produit': self.farine.pk, 'quantite': '0.500', 'unite': 'kg'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        auth(self.resp).post(
            f'/api/django/hospitality/recettes/{recette.pk}/ingredients/',
            {'produit': self.beurre.pk, 'quantite': '0.200', 'unite': 'kg'},
            format='json',
        )

        detail = auth(self.normal).get(
            f'/api/django/hospitality/recettes/{recette.pk}/')
        self.assertEqual(len(detail.data['ingredients']), 2)
        quantites = {
            i['produit_nom']: i['quantite'] for i in detail.data['ingredients']}
        self.assertEqual(quantites['Farine'], '0.500')
        self.assertEqual(quantites['Beurre'], '0.200')

    def test_ingredient_produit_autre_societe_refuse(self):
        from apps.stock.models import Produit

        autre_co = make_company('hot-rec-b', 'B')
        produit_b = Produit.objects.create(
            company=autre_co, nom='Sucre B', prix_achat=Decimal('3'),
            prix_vente=Decimal('5'))
        recette = Recette.objects.create(
            company=self.co, nom_plat='Tarte', prix_vente_ht=Decimal('45'))
        resp = auth(self.resp).post(
            f'/api/django/hospitality/recettes/{recette.pk}/ingredients/',
            {'produit': produit_b.pk, 'quantite': '1', 'unite': 'kg'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(IngredientRecette.objects.count(), 0)

    def test_ajout_ingredient_refuse_pour_role_normal(self):
        recette = Recette.objects.create(
            company=self.co, nom_plat='Tarte', prix_vente_ht=Decimal('45'))
        resp = auth(self.normal).post(
            f'/api/django/hospitality/recettes/{recette.pk}/ingredients/',
            {'produit': self.farine.pk, 'quantite': '1', 'unite': 'kg'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_tenant_isolation(self):
        autre_co = make_company('hot-rec-c', 'C')
        autre_user = make_user(autre_co, 'hot-rec-c-user')
        Recette.objects.create(
            company=self.co, nom_plat='Tarte secrète', prix_vente_ht=Decimal('45'))
        resp = auth(autre_user).get('/api/django/hospitality/recettes/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)
