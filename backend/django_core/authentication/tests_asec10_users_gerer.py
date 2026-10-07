"""ASEC10 / D-ASEC-4 — ``users_gerer`` appliqué côté serveur.

Un rôle de palier responsable SANS ``users_gerer`` reçoit 403
``droit_manquant`` sur toute écriture ``/users/`` (création, modification,
suppression) ; AVEC le code, la garde de rang d'ASEC2 s'applique ensuite ; la
lecture reste ouverte ; un non-administrateur ne retire pas ``roles_gerer``
d'un rôle administrateur personnalisé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()


class UsersGererTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC10', slug='asec10-co')
        self.r_dir = Role.objects.create(
            company=self.company, nom='Directeur', est_systeme=True,
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.r_sans = Role.objects.create(
            company=self.company, nom='Chef sans comptes',
            permissions=['users_voir', 'crm_voir', 'crm_creer'])
        self.r_avec = Role.objects.create(
            company=self.company, nom='Chef avec comptes',
            permissions=['users_voir', 'users_gerer', 'crm_voir', 'crm_creer'])
        self.r_base = Role.objects.create(
            company=self.company, nom='Vendeur', permissions=['crm_voir'])
        self.directeur = User.objects.create_user(
            username='asec10_dir', password='x', company=self.company,
            role=self.r_dir, is_protected=True)
        self.sans = User.objects.create_user(
            username='asec10_sans', password='x', company=self.company,
            role=self.r_sans)
        self.avec = User.objects.create_user(
            username='asec10_avec', password='x', company=self.company,
            role=self.r_avec)
        self.cible = User.objects.create_user(
            username='asec10_cible', password='x', email='c@x.ma',
            company=self.company, role=self.r_base)

    def _api(self, u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    def _refus(self, resp):
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', None))
        self.assertEqual(resp.data.get('code'), 'droit_manquant', resp.data)

    def test_sans_code_ecriture_refusee(self):
        api = self._api(self.sans)
        self._refus(api.post(
            '/api/django/users/',
            {'username': 'asec10_new', 'password': 'Nouveau-mdp-456!'},
            format='json'))
        self.assertFalse(User.objects.filter(username='asec10_new').exists())
        self._refus(api.patch(
            f'/api/django/users/{self.cible.id}/', {'email': 'p@x.ma'},
            format='json'))
        self._refus(api.delete(f'/api/django/users/{self.cible.id}/'))
        cible = User.objects.get(pk=self.cible.pk)
        self.assertEqual(cible.email, 'c@x.ma')
        self.assertTrue(cible.is_active)

    def test_avec_code_garde_de_rang_appliquee(self):
        api = self._api(self.avec)
        resp = api.patch(
            f'/api/django/users/{self.cible.id}/', {'poste': 'Vendeur'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = api.patch(
            f'/api/django/users/{self.directeur.id}/', {'email': 'p@x.ma'},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data.get('code'), 'rang_cible')

    def test_lecture_inchangee(self):
        api = self._api(self.sans)
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        self.assertEqual(
            api.get(f'/api/django/users/{self.cible.id}/').status_code, 200)

    def test_non_admin_ne_retire_pas_roles_gerer(self):
        admin_perso = Role.objects.create(
            company=self.company, nom='Admin maison',
            permissions=['roles_gerer', 'users_voir', 'users_gerer'])
        resp = self._api(self.avec).patch(
            f'/api/django/roles/{admin_perso.id}/',
            {'permissions': ['users_voir', 'users_gerer']}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        admin_perso.refresh_from_db()
        self.assertIn('roles_gerer', admin_perso.permissions)
