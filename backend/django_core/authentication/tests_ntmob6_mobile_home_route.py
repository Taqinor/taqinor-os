"""NTMOB6 — Sélecteur de démarrage par rôle (accueil mobile mémorisé).

Couvre :
- ``mobile_home_route`` par défaut = NULL (comportement inchangé pour tout
  compte existant tant qu'il ne se connecte pas d'un viewport mobile) ;
- ``selectors.default_mobile_home_route`` : Technicien → ``/ma-journee``,
  Commercial → ``/mobile/commercial``, Directeur/Administrateur →
  ``/mobile/cockpit``, tout autre rôle (ou compte hérité normal) → ``''`` ;
- l'endpoint self-service persiste UNIQUEMENT le compte courant, rejette une
  route hors whitelist, et accepte ``null`` pour revenir à l'état
  « pas encore décidé ».
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company, CustomUser
from authentication.selectors import default_mobile_home_route


def _make_company(name='MobHome Co', slug='mobhome-co'):
    return Company.objects.create(nom=name, slug=slug)


def _make_user(company, username, role_nom=None, role_legacy=CustomUser.ROLE_NORMAL):
    role = None
    if role_nom:
        role = Role.objects.create(company=company, nom=role_nom, permissions=[])
    return CustomUser.objects.create_user(
        username=username, password='pw', company=company,
        role=role, role_legacy=role_legacy)


class MobileHomeRouteFieldTests(TestCase):
    def test_default_is_null(self):
        company = _make_company()
        user = _make_user(company, 'plain')
        self.assertIsNone(user.mobile_home_route)


class DefaultMobileHomeRouteSelectorTests(TestCase):
    def setUp(self):
        self.company = _make_company('SelectorCo', 'selector-co')

    def test_technicien(self):
        user = _make_user(self.company, 'tech1', role_nom='Technicien')
        self.assertEqual(default_mobile_home_route(user), '/ma-journee')

    def test_technicien_responsable_falls_back_to_technicien_prefix(self):
        user = _make_user(self.company, 'tech2', role_nom='Technicien responsable')
        self.assertEqual(default_mobile_home_route(user), '/ma-journee')

    def test_commercial(self):
        user = _make_user(self.company, 'com1', role_nom='Commercial')
        self.assertEqual(default_mobile_home_route(user), '/mobile/commercial')

    def test_commercial_responsable_falls_back_to_commercial_prefix(self):
        user = _make_user(self.company, 'com2', role_nom='Commercial responsable')
        self.assertEqual(default_mobile_home_route(user), '/mobile/commercial')

    def test_directeur(self):
        user = _make_user(self.company, 'dir1', role_nom='Directeur')
        self.assertEqual(default_mobile_home_route(user), '/mobile/cockpit')

    def test_administrateur(self):
        user = _make_user(self.company, 'adm1', role_nom='Administrateur')
        self.assertEqual(default_mobile_home_route(user), '/mobile/cockpit')

    def test_unmapped_role_falls_back_to_dashboard(self):
        user = _make_user(self.company, 'viewer1', role_nom='Viewer')
        self.assertEqual(default_mobile_home_route(user), '')

    def test_legacy_account_without_fine_role_defaults_to_dashboard(self):
        user = _make_user(self.company, 'legacy1')
        self.assertEqual(default_mobile_home_route(user), '')

    def test_legacy_admin_without_fine_role_maps_to_cockpit(self):
        user = _make_user(
            self.company, 'legacyadmin', role_legacy=CustomUser.ROLE_ADMIN)
        self.assertEqual(default_mobile_home_route(user), '/mobile/cockpit')


class MobileHomeRouteApiTests(TestCase):
    def setUp(self):
        self.company = _make_company('ApiCo', 'api-co')
        self.alice = _make_user(self.company, 'alice', role_nom='Commercial')
        self.bob = _make_user(self.company, 'bob', role_nom='Technicien')
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def test_persists_chosen_route(self):
        res = self.client.post(
            '/api/django/auth/mobile-home-route/',
            {'route': '/mobile/commercial'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['mobile_home_route'], '/mobile/commercial')
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.mobile_home_route, '/mobile/commercial')

    def test_opt_out_stores_empty_string(self):
        res = self.client.post(
            '/api/django/auth/mobile-home-route/',
            {'route': ''}, format='json')
        self.assertEqual(res.status_code, 200)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.mobile_home_route, '')

    def test_null_resets_to_undecided(self):
        self.alice.mobile_home_route = '/mobile/commercial'
        self.alice.save(update_fields=['mobile_home_route'])
        res = self.client.post(
            '/api/django/auth/mobile-home-route/',
            {'route': None}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['mobile_home_route'])
        self.alice.refresh_from_db()
        self.assertIsNone(self.alice.mobile_home_route)

    def test_rejects_route_outside_whitelist(self):
        res = self.client.post(
            '/api/django/auth/mobile-home-route/',
            {'route': '/admin/nuke'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.alice.refresh_from_db()
        self.assertIsNone(self.alice.mobile_home_route)

    def test_only_affects_current_user(self):
        self.client.post(
            '/api/django/auth/mobile-home-route/',
            {'route': '/mobile/commercial'}, format='json')
        self.bob.refresh_from_db()
        self.assertIsNone(self.bob.mobile_home_route)

    def test_returned_in_me_endpoint(self):
        self.alice.mobile_home_route = '/mobile/commercial'
        self.alice.save(update_fields=['mobile_home_route'])
        res = self.client.get('/api/django/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['mobile_home_route'], '/mobile/commercial')

    def test_me_patch_cannot_write_mobile_home_route(self):
        # NTMOB6 — écriture réservée à l'endpoint dédié (whitelist stricte) ;
        # le PATCH générique de profil doit rester read-only sur ce champ.
        res = self.client.patch(
            '/api/django/auth/me/', {'mobile_home_route': '/mobile/cockpit'},
            format='json')
        self.assertIn(res.status_code, (200, 405))  # RetrieveAPIView : pas de PATCH
        self.alice.refresh_from_db()
        self.assertIsNone(self.alice.mobile_home_route)
