"""ASEC2 — la gestion des comptes est bornée au RANG de la cible.

Les trois paliers « responsable » (Commercial responsable, Technicien
responsable, Admin RH) reçoivent 403 ``rang_cible`` sur un Directeur protégé
ou un second propriétaire, et ne s'attribuent pas un rôle plus large que le
leur (403 ``role_plus_large``). Chaque refus laisse la cible strictement
inchangée (relecture en base). Un Directeur agissant sur un palier inférieur
garde le comportement 200 d'origine.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_PERMISSIONS,
    ADMIN_RH_PERMISSIONS,
    COMMERCIAL_PERMISSIONS,
    COMMERCIAL_RESP_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()

_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40


class RangCibleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC2 Co', slug='asec2-co')

        def role(nom, perms):
            return Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms),
                est_systeme=True)

        self.r_dir = role('Directeur', DIRECTEUR_PERMISSIONS)
        self.r_adm = role('Administrateur', ADMIN_PERMISSIONS)
        self.r_cresp = role('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS)
        self.r_tresp = role('Technicien responsable', TECHNICIEN_RESP_PERMISSIONS)
        self.r_rh = role('Admin RH', ADMIN_RH_PERMISSIONS)
        self.r_com = role('Commercial', COMMERCIAL_PERMISSIONS)

        def user(name, r, **kw):
            return User.objects.create_user(
                username=name, password='Ancien-mdp-123', email=f'{name}@x.ma',
                company=self.company, role=r, **kw)

        self.directeur = user('asec2_dir', self.r_dir, is_protected=True)
        self.second = user('asec2_adm', self.r_adm)
        self.cresp = user('asec2_cresp', self.r_cresp)
        self.tresp = user('asec2_tresp', self.r_tresp)
        self.rh = user('asec2_rh', self.r_rh)
        self.commercial = user('asec2_com', self.r_com)
        self.responsables = [self.cresp, self.tresp, self.rh]

    def _api(self, u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    def _etat(self, u):
        u = User.objects.get(pk=u.pk)
        return (u.check_password('Ancien-mdp-123'), u.is_active, u.email,
                u.role_id, u.avatar_key, u.must_change_password)

    def _assert_refus(self, resp, code='rang_cible'):
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', None))
        self.assertEqual(resp.data.get('code'), code, resp.data)

    def test_responsable_refuse_sur_directeur_protege(self):
        gestes = [
            {'password': 'Nouveau-mdp-456!'},
            {'email': 'pirate@x.ma'},
            {'is_active': False},
            {'role': self.r_com.id},
            {'must_change_password': True},
        ]
        avant = self._etat(self.directeur)
        for acteur in self.responsables:
            api = self._api(acteur)
            for corps in gestes:
                with self.subTest(acteur=acteur.username, corps=corps):
                    resp = api.patch(
                        f'/api/django/users/{self.directeur.id}/', corps,
                        format='json')
                    self.assertEqual(resp.status_code, 403, resp.data)
                    self.assertEqual(self._etat(self.directeur), avant)
            with self.subTest(acteur=acteur.username, geste='avatar'):
                resp = api.post(
                    f'/api/django/users/{self.directeur.id}/avatar/',
                    {'file': SimpleUploadedFile('a.png', _PNG, 'image/png')},
                    format='multipart')
                self._assert_refus(resp)
                self.assertEqual(self._etat(self.directeur), avant)

    def test_responsable_refuse_sur_second_proprietaire(self):
        avant = self._etat(self.second)
        for acteur in self.responsables:
            api = self._api(acteur)
            with self.subTest(acteur=acteur.username, geste='email'):
                resp = api.patch(
                    f'/api/django/users/{self.second.id}/',
                    {'email': 'pirate@x.ma'}, format='json')
                self._assert_refus(resp)
            with self.subTest(acteur=acteur.username, geste='DELETE'):
                resp = api.delete(f'/api/django/users/{self.second.id}/')
                self._assert_refus(resp)
            self.assertEqual(self._etat(self.second), avant)
            self.assertTrue(User.objects.filter(pk=self.second.pk).exists())

    def test_role_plus_large_auto_attribue_refuse(self):
        large = Role.objects.create(
            company=self.company, nom='Perso large',
            permissions=list(COMMERCIAL_RESP_PERMISSIONS) + ['paie_gerer'])
        resp = self._api(self.cresp).patch(
            f'/api/django/users/{self.cresp.id}/', {'role': large.id},
            format='json')
        self._assert_refus(resp, code='role_plus_large')
        self.cresp.refresh_from_db()
        self.assertEqual(self.cresp.role_id, self.r_cresp.id)

    def test_responsable_sur_palier_inferieur_reste_200(self):
        resp = self._api(self.cresp).patch(
            f'/api/django/users/{self.commercial.id}/', {'poste': 'Vendeur'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_admin_sur_palier_inferieur_200(self):
        api = self._api(self.directeur)
        resp = api.patch(
            f'/api/django/users/{self.cresp.id}/',
            {'email': 'nouveau@x.ma', 'must_change_password': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cresp.refresh_from_db()
        self.assertEqual(self.cresp.email, 'nouveau@x.ma')
        resp = api.patch(
            f'/api/django/users/{self.commercial.id}/', {'role': self.r_cresp.id},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
