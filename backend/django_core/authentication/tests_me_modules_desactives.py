"""ODX6 — ``/auth/me/`` expose la liste des modules DÉSACTIVÉS de la société.

Le frontend lit ce champ au bootstrap pour masquer la navigation des modules
désactivés et bloquer leurs routes. Invariants testés :
  - défaut (aucun ``ModuleToggle``) → liste VIDE (nav strictement inchangée) ;
  - un module désactivé apparaît dans la liste ;
  - un module ré-activé (toggle ``actif=True``) n'apparaît pas ;
  - ISOLEMENT multi-tenant : le toggle de la société A ne fuit pas dans le
    ``/auth/me/`` d'un utilisateur de la société B.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ALL_PERMISSIONS
from core.models import ModuleToggle

User = get_user_model()


class MeModulesDesactivesTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(nom='Alpha', slug='alpha')
        self.company_b = Company.objects.create(nom='Beta', slug='beta')
        self.role_a = Role.objects.create(
            company=self.company_a, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.role_b = Role.objects.create(
            company=self.company_b, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.user_a = User.objects.create_user(
            username='a', password='x', role=self.role_a,
            role_legacy='admin', company=self.company_a)
        self.user_b = User.objects.create_user(
            username='b', password='x', role=self.role_b,
            role_legacy='admin', company=self.company_b)

    def _me(self, user):
        api = APIClient()
        token = str(AccessToken.for_user(user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api.get('/api/django/auth/me/')

    def test_defaut_liste_vide(self):
        resp = self._me(self.user_a)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('modules_desactives', resp.data)
        self.assertEqual(list(resp.data['modules_desactives']), [])

    def test_module_desactive_apparait(self):
        ModuleToggle.objects.create(
            company=self.company_a, module='flotte', actif=False)
        resp = self._me(self.user_a)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('flotte', resp.data['modules_desactives'])

    def test_module_reactive_absent(self):
        ModuleToggle.objects.create(
            company=self.company_a, module='flotte', actif=True)
        resp = self._me(self.user_a)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('flotte', resp.data['modules_desactives'])

    def test_isolement_multi_tenant(self):
        # Société A désactive « flotte » ; l'utilisateur de la société B ne
        # doit RIEN voir de ce toggle.
        ModuleToggle.objects.create(
            company=self.company_a, module='flotte', actif=False)
        resp_b = self._me(self.user_b)
        self.assertEqual(resp_b.status_code, 200)
        self.assertEqual(list(resp_b.data['modules_desactives']), [])
        # A, elle, le voit bien.
        resp_a = self._me(self.user_a)
        self.assertIn('flotte', resp_a.data['modules_desactives'])
