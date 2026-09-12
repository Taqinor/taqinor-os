"""NTI18N12 — préférence d'affichage « calendrier hégirien » (jamais stocké).

Couvre : défaut False, endpoint self-service (PATCH /auth/me/calendrier-
hegirien/, ouvert à IsAuthenticated — pas besoin d'être admin/responsable),
isolation entre utilisateurs, exposition via /auth/me/, ET éditable via le
PATCH générique du profil (UserViewSet, Équipe & rôles — contrairement à
langue_interface).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser


def _company(slug='nti18n12-co', nom='NTI18N12 Co'):
    return Company.objects.create(nom=nom, slug=slug)


def _user(company, username, **kwargs):
    return CustomUser.objects.create_user(
        username=username, password='pw', company=company, **kwargs)


class CalendrierHegirienFieldTests(TestCase):
    def test_default_is_false(self):
        company = _company()
        user = _user(company, 'plain12')
        self.assertFalse(user.calendrier_hegirien)


class CalendrierHegirienSelfServiceApiTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n12-co2', 'NTI18N12 Co2')
        # Rôle LIMITÉ (aucun accès à Équipe & rôles) : prouve que le réglage
        # de SA PROPRE préférence n'exige pas IsAdminOrResponsableTier.
        self.commercial = _user(
            self.company, 'commercial12', role_legacy=CustomUser.ROLE_NORMAL)
        self.autre = _user(self.company, 'autre12')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.commercial)}')

    def test_limited_role_can_toggle_own_preference(self):
        resp = self.api.patch(
            '/api/django/auth/me/calendrier-hegirien/',
            {'calendrier_hegirien': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['calendrier_hegirien'])
        self.commercial.refresh_from_db()
        self.assertTrue(self.commercial.calendrier_hegirien)

    def test_rejects_non_boolean_value(self):
        resp = self.api.patch(
            '/api/django/auth/me/calendrier-hegirien/',
            {'calendrier_hegirien': 'oui'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_only_affects_current_user(self):
        self.api.patch(
            '/api/django/auth/me/calendrier-hegirien/',
            {'calendrier_hegirien': True}, format='json')
        self.autre.refresh_from_db()
        self.assertFalse(self.autre.calendrier_hegirien)

    def test_returned_in_me_endpoint(self):
        self.commercial.calendrier_hegirien = True
        self.commercial.save(update_fields=['calendrier_hegirien'])
        resp = self.api.get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['calendrier_hegirien'])


class CalendrierHegirienAdminEditTests(TestCase):
    """Équipe & rôles : un admin peut préparer le réglage d'un membre via le
    PATCH générique du profil (UserViewSet) — contrairement à
    langue_interface, ce champ N'EST PAS en lecture seule côté serializer."""

    def setUp(self):
        self.company = _company('nti18n12-co3', 'NTI18N12 Co3')
        self.admin = _user(
            self.company, 'admin12', role_legacy=CustomUser.ROLE_ADMIN)
        self.membre = _user(
            self.company, 'membre12', role_legacy=CustomUser.ROLE_NORMAL)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_admin_can_set_member_preference_via_users_endpoint(self):
        resp = self.api.patch(
            f'/api/django/users/{self.membre.id}/',
            {'calendrier_hegirien': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.calendrier_hegirien)
