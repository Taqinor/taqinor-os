"""XSAL1 — Listes de prix clients (détail / revendeur / export).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal1_listes_prix -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import CustomUser
from apps.ventes.models import ListePrix, LignePrixListe
from apps.ventes.services import prix_applicable
from testkit.factories import (
    CompanyFactory, ClientFactory, ProduitFactory, UserFactory, another_tenant,
)


class TestPrixApplicableResolution(TestCase):
    """XSAL1 — service `prix_applicable` (résolution liste client)."""

    def setUp(self):
        self.company = CompanyFactory()
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'),
            prix_achat=Decimal('600.00'))
        self.client_sans_liste = ClientFactory(company=self.company)
        self.liste = ListePrix.objects.create(
            company=self.company, nom='Revendeur')
        self.client_revendeur = ClientFactory(
            company=self.company, liste_prix=self.liste)

    def test_client_sans_liste_garde_prix_vente(self):
        resolved = prix_applicable(
            produit=self.produit, client=self.client_sans_liste, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_client_none_garde_prix_vente(self):
        resolved = prix_applicable(produit=self.produit, client=None, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))

    def test_liste_prix_ligne_fixe_prefill(self):
        LignePrixListe.objects.create(
            liste=self.liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_revendeur, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('850.00'))
        self.assertEqual(resolved['source'], 'liste')
        self.assertEqual(resolved['liste_nom'], 'Revendeur')

    def test_archived_liste_falls_back_to_standard(self):
        self.liste.archived = True
        self.liste.save()
        LignePrixListe.objects.create(
            liste=self.liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_revendeur, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_never_exposes_prix_achat(self):
        resolved = prix_applicable(
            produit=self.produit, client=self.client_revendeur, quantite=1)
        self.assertNotIn('prix_achat', resolved)


class TestListePrixViewSetTenantIsolation(TestCase):
    """XSAL1 — le ViewSet reste company-scoped, écriture responsable/admin."""

    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_ADMIN)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.liste = ListePrix.objects.create(
            company=self.company, nom='Export')

    def _api_for(self, user):
        api = APIClient()
        token = AccessToken.for_user(user)
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api

    def test_admin_can_create_liste(self):
        api = self._api_for(self.admin)
        resp = api.post('/api/django/ventes/listes-prix/', {
            'nom': 'Nouvelle liste', 'devise': 'MAD',
        })
        self.assertEqual(resp.status_code, 201)
        created = ListePrix.objects.get(id=resp.data['id'])
        self.assertEqual(created.company_id, self.company.id)

    def test_company_forced_server_side_ignores_body_override(self):
        other_company, _ = another_tenant()
        api = self._api_for(self.admin)
        resp = api.post('/api/django/ventes/listes-prix/', {
            'nom': 'Hack', 'company': other_company.id,
        })
        self.assertEqual(resp.status_code, 201)
        created = ListePrix.objects.get(id=resp.data['id'])
        self.assertEqual(created.company_id, self.company.id)

    def test_normal_role_forbidden_from_creating(self):
        api = self._api_for(self.normal)
        resp = api.post('/api/django/ventes/listes-prix/', {'nom': 'X'})
        self.assertEqual(resp.status_code, 403)

    def test_cross_tenant_list_hidden(self):
        _other_company, other_user = another_tenant()
        api = self._api_for(other_user)
        resp = api.get('/api/django/ventes/listes-prix/')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.data.get('results', resp.data)]
        self.assertNotIn(self.liste.id, ids)

    def test_lignes_action_upserts_price(self):
        produit = ProduitFactory(company=self.company, prix_vente=Decimal('500'))
        api = self._api_for(self.admin)
        resp = api.post(
            f'/api/django/ventes/listes-prix/{self.liste.id}/lignes/',
            {'produit': produit.id, 'prix_unitaire': '420.00'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            LignePrixListe.objects.filter(
                liste=self.liste, produit=produit,
                prix_unitaire=Decimal('420.00')).exists())
