"""XSAL2 — Règles de prix + paliers de quantité (remises volume automatiques).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal2_regles_paliers -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import CustomUser
from apps.ventes.models import ListePrix, RegleListePrix
from apps.ventes.services import prix_applicable
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory, UserFactory


class TestReglesPaliersQuantite(TestCase):
    """XSAL2 — règles de prix + paliers de quantité, priorité de portée."""

    def setUp(self):
        self.company = CompanyFactory()
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        self.liste = ListePrix.objects.create(company=self.company, nom='Gros')
        self.client = ClientFactory(company=self.company, liste_prix=self.liste)

    def test_palier_atteint_applique_remise(self):
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.REMISE_PCT,
            valeur=Decimal('8'), quantite_min=Decimal('5'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=6)
        self.assertEqual(resolved['prix'], Decimal('920.00'))
        self.assertEqual(resolved['source'], 'regle')

    def test_sous_palier_utilise_prix_de_base(self):
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.REMISE_PCT,
            valeur=Decimal('8'), quantite_min=Decimal('5'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=2)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_produit_prevaut_sur_categorie(self):
        from apps.stock.models import Categorie
        cat = Categorie.objects.create(company=self.company, nom='Onduleurs')
        self.produit.categorie = cat
        self.produit.save()
        RegleListePrix.objects.create(
            liste=self.liste, categorie_nom='Onduleurs',
            type_regle=RegleListePrix.TypeRegle.REMISE_PCT,
            valeur=Decimal('5'), quantite_min=Decimal('1'))
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.REMISE_PCT,
            valeur=Decimal('15'), quantite_min=Decimal('1'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=1)
        # La règle produit (spécificité 3) l'emporte sur la catégorie (2).
        self.assertEqual(resolved['prix'], Decimal('850.00'))

    def test_prix_fixe_ignore_prix_de_base(self):
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.PRIX_FIXE,
            valeur=Decimal('777.77'), quantite_min=Decimal('1'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('777.77'))

    def test_formule_sur_prix_vente(self):
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.FORMULE_SUR_PRIX_VENTE,
            valeur=Decimal('0.9'), quantite_min=Decimal('1'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('900.00'))

    def test_inactive_rule_ignored(self):
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit, actif=False,
            type_regle=RegleListePrix.TypeRegle.PRIX_FIXE,
            valeur=Decimal('1.00'), quantite_min=Decimal('1'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_never_exposes_prix_achat(self):
        RegleListePrix.objects.create(
            liste=self.liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.REMISE_PCT,
            valeur=Decimal('8'), quantite_min=Decimal('1'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client, quantite=1)
        self.assertNotIn('prix_achat', resolved)


class TestReglesViewSetAction(TestCase):
    """XSAL2 — POST /ventes/listes-prix/{id}/regles/ (responsable/admin only)."""

    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_ADMIN)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.produit = ProduitFactory(company=self.company)
        self.liste = ListePrix.objects.create(company=self.company, nom='Gros')

    def _api_for(self, user):
        api = APIClient()
        token = AccessToken.for_user(user)
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api

    def test_admin_can_add_rule(self):
        api = self._api_for(self.admin)
        resp = api.post(
            f'/api/django/ventes/listes-prix/{self.liste.id}/regles/',
            {
                'produit': self.produit.id,
                'type_regle': RegleListePrix.TypeRegle.REMISE_PCT,
                'valeur': '8',
                'quantite_min': '5',
            })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            RegleListePrix.objects.filter(liste=self.liste, produit=self.produit).exists())

    def test_normal_role_forbidden(self):
        api = self._api_for(self.normal)
        resp = api.post(
            f'/api/django/ventes/listes-prix/{self.liste.id}/regles/',
            {
                'type_regle': RegleListePrix.TypeRegle.PRIX_FIXE,
                'valeur': '1',
            })
        self.assertEqual(resp.status_code, 403)
