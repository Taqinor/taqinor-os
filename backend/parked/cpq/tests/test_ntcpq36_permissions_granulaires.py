"""NTCPQ36 — Permissions granulaires CPQ dans ``roles.Role``.

``cpq_marge_voir`` conditionne l'exposition de ``marge_sous_seuil`` (NTCPQ6)
sur le détail devis : un utilisateur à rôle FIN sans cette permission ne la
voit jamais, même authentifié en interne ; un staff avec la permission la
reçoit. Un compte SANS rôle fin (légacy) garde le comportement historique
(visible) — aucune régression pour les tenants existants.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import ALL_PERMISSIONS, Role
from apps.ventes.models import LigneDevis
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, DevisFactory, ProduitFactory, UserFactory


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestMargeSousSeuilPermission(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        produit = ProduitFactory(
            company=self.company, prix_achat=Decimal('600.00'),
            prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(company=self.company)
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Onduleur',
            quantite=1, prix_unitaire=Decimal('1000.00'))

    def _detail_url(self):
        return f'/api/django/ventes/devis/{self.devis.id}/'

    def test_legacy_sans_role_fin_voit_le_champ(self):
        legacy = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        resp = auth(legacy).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('marge_sous_seuil', resp.data)

    def test_role_fin_sans_permission_ne_voit_pas_le_champ(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial sans marge',
            permissions=[p for p in ALL_PERMISSIONS if p != 'cpq_marge_voir'])
        user = UserFactory(company=self.company, role=role)
        resp = auth(user).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('marge_sous_seuil', resp.data)

    def test_role_fin_avec_permission_voit_le_champ(self):
        role = Role.objects.create(
            company=self.company, nom='Staff avec marge',
            permissions=['cpq_marge_voir', 'ventes_voir'])
        user = UserFactory(company=self.company, role=role)
        resp = auth(user).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('marge_sous_seuil', resp.data)

    def test_directeur_porte_la_permission_par_defaut(self):
        from apps.roles.models import DIRECTEUR_PERMISSIONS
        self.assertIn('cpq_marge_voir', DIRECTEUR_PERMISSIONS)

    def test_responsable_ne_porte_pas_la_permission_par_defaut(self):
        from apps.roles.models import RESPONSABLE_PERMISSIONS
        self.assertNotIn('cpq_marge_voir', RESPONSABLE_PERMISSIONS)
