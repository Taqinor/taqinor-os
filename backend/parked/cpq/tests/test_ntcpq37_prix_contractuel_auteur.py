"""NTCPQ37 — Restriction ``PrixContractuel`` : seul le créateur ou un rôle
supérieur (``cpq_prix_contractuels_gerer``) peut modifier/supprimer."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import PrixContractuel
from apps.roles.models import ALL_PERMISSIONS, Role
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory, UserFactory


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestPrixContractuelAuteur(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.client_obj = ClientFactory(company=self.company)
        self.produit = ProduitFactory(company=self.company)
        self.auteur = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.collegue = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.prix = PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('900.00'),
            created_by=self.auteur)

    def _url(self):
        return f'/api/django/cpq/prix-contractuels/{self.prix.id}/'

    def test_auteur_peut_modifier(self):
        resp = auth(self.auteur).patch(
            self._url(), {'prix_ht': '950.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_collegue_legacy_responsable_garde_lacces_historique(self):
        """Repli légacy (``HasPermissionOrLegacy``) : un compte SANS rôle
        fin (``role_legacy`` seul) garde le comportement HISTORIQUE
        (n'importe quel Responsable pouvait déjà éditer n'importe quel
        PrixContractuel via l'ancien ``IsResponsableOrAdmin`` sans notion
        d'auteur) — aucune régression pour les tenants non encore migrés
        vers le système de rôles fins."""
        resp = auth(self.collegue).patch(
            self._url(), {'prix_ht': '950.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_role_fin_avec_permission_elevee_peut_modifier(self):
        role = Role.objects.create(
            company=self.company, nom='Directeur test',
            permissions=ALL_PERMISSIONS)
        directeur = UserFactory(company=self.company, role=role)
        resp = auth(directeur).patch(
            self._url(), {'prix_ht': '950.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_role_fin_sans_permission_refuse(self):
        role = Role.objects.create(
            company=self.company, nom='Responsable sans code',
            permissions=[p for p in ALL_PERMISSIONS
                         if p != 'cpq_prix_contractuels_gerer'])
        autre = UserFactory(company=self.company, role=role)
        resp = auth(autre).patch(
            self._url(), {'prix_ht': '950.00'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_suppression_meme_regle(self):
        role = Role.objects.create(
            company=self.company, nom='Sans droit suppression',
            permissions=[p for p in ALL_PERMISSIONS
                         if p != 'cpq_prix_contractuels_gerer'])
        autre = UserFactory(company=self.company, role=role)
        resp = auth(autre).delete(self._url())
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            PrixContractuel.objects.filter(id=self.prix.id).exists())
        resp2 = auth(self.auteur).delete(self._url())
        self.assertEqual(resp2.status_code, 204)
