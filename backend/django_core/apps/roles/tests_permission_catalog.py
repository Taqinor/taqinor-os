"""YRBAC10 — endpoint catalogue de permissions (source unique du gating).

``GET /api/django/roles/permission-catalog/`` (Administrateur uniquement) sert
la matrice ``ALL_PERMISSIONS`` + une carte route→rôles enforced dérivée de la
matrice canonique YRBAC2 (``core.rbac_matrix``). Invariants testés :

  - un Administrateur reçoit 200 avec ``permissions`` (non vide) et ``routes`` ;
  - chaque entrée ``routes`` porte path/method/allowed_roles cohérents avec la
    matrice (dérivation, pas de liste parallèle) ;
  - un rôle NON administrateur (Responsable sans ``roles_gerer``) reçoit 403
    (surface admin, jamais élargie) ;
  - un anonyme reçoit 401/403.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ALL_PERMISSIONS
from core.rbac_matrix import MATRIX, ALLOW

User = get_user_model()

CATALOG_URL = '/api/django/roles/permission-catalog/'


class PermissionCatalogTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cat Co', slug='cat-co')
        # Administrateur : porte roles_gerer (⇒ is_admin_role True).
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='cat_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        # Responsable SANS roles_gerer : palier promu mais pas administrateur.
        resp_perms = [p for p in ALL_PERMISSIONS if p != 'roles_gerer']
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=resp_perms, est_systeme=True)
        self.responsable = User.objects.create_user(
            username='cat_resp', password='x', role=self.resp_role,
            company=self.company)

    def _client_for(self, user):
        api = APIClient()
        token = str(AccessToken.for_user(user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api

    def test_admin_recoit_catalogue(self):
        resp = self._client_for(self.admin).get(CATALOG_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('permissions', resp.data)
        self.assertIn('routes', resp.data)
        self.assertEqual(list(resp.data['permissions']), list(ALL_PERMISSIONS))
        self.assertTrue(len(resp.data['permissions']) > 0)

    def test_routes_derivees_de_la_matrice(self):
        resp = self._client_for(self.admin).get(CATALOG_URL)
        routes = resp.data['routes']
        # Une entrée par ligne de matrice (dérivation 1:1).
        self.assertEqual(len(routes), len(MATRIX))
        by_key = {(r['method'], r['path']): r for r in routes}
        for entry in MATRIX:
            r = by_key[(entry.method, entry.path)]
            expected = sorted(
                n for n, v in entry.verdicts.items() if v == ALLOW)
            self.assertEqual(r['allowed_roles'], expected)
            self.assertEqual(r['app'], entry.app)

    def test_non_admin_403(self):
        # Responsable promu mais sans roles_gerer : la surface catalogue reste
        # réservée à l'Administrateur (jamais élargie).
        resp = self._client_for(self.responsable).get(CATALOG_URL)
        self.assertEqual(resp.status_code, 403)

    def test_anonyme_refuse(self):
        resp = APIClient().get(CATALOG_URL)
        self.assertIn(resp.status_code, (401, 403))
