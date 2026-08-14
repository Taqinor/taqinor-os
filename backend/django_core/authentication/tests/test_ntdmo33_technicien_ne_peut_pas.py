"""NTDMO33 — le mode présentation (NTDMO10) et le toggle `tours_actifs`
(NTDMO27), tous deux exposés par ``PATCH /companies/{id}/``, restent
invisibles/inaccessibles aux rôles Technicien/Terrain.

Pas de nouvelle permission dédiée (« jamais une permission redondante ») :
``CompanyViewSet`` est déjà gardé par ``IsAdminUser`` (``request.user.
is_staff``), que seul un compte admin/démo explicitement promu porte — un
rôle Technicien n'a JAMAIS ``is_staff=True``. Ce test VERROUILLE ce
comportement par régression (un futur changement qui l'affaiblirait ferait
échouer ce test)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role

User = get_user_model()


class TechnicienCannotToggleDemoSettingsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Démo Terrain', slug='co-demo-terrain-33', est_demo=True)
        self.role_technicien = Role.objects.create(
            company=self.company, nom='Technicien')
        self.technicien = User.objects.create_user(
            'tech-33', password='x', company=self.company,
            role=self.role_technicien, is_staff=False)
        # Compte admin réel (is_staff=True, même garde que seed_demo_company)
        # pour prouver que le test discrimine bien is_staff, pas juste
        # « aucun accès ».
        self.admin = User.objects.create_user(
            'admin-33', password='x', company=self.company, is_staff=True)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_technicien_gets_403_on_mode_presentation_toggle(self):
        r = self._client(self.technicien).patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': True})
        self.assertEqual(r.status_code, 403)
        self.company.refresh_from_db()
        self.assertFalse(self.company.mode_presentation_actif)

    def test_technicien_gets_403_on_tours_actifs_toggle(self):
        r = self._client(self.technicien).patch(
            f'/api/django/companies/{self.company.id}/',
            {'tours_actifs': False})
        self.assertEqual(r.status_code, 403)
        self.company.refresh_from_db()
        self.assertTrue(self.company.tours_actifs)

    def test_technicien_gets_403_on_reset_demo(self):
        r = self._client(self.technicien).post(
            f'/api/django/companies/{self.company.id}/reset-demo/')
        self.assertEqual(r.status_code, 403)

    def test_technicien_cannot_even_read_company_detail(self):
        # IsAdminUser gate le VIEWSET entier (list/retrieve compris) : un
        # technicien ne peut même pas LIRE la fiche société via cet endpoint.
        r = self._client(self.technicien).get(
            f'/api/django/companies/{self.company.id}/')
        self.assertEqual(r.status_code, 403)

    def test_a_real_admin_can_toggle_it(self):
        # Discrimine bien is_staff (pas juste « personne n'entre jamais »).
        r = self._client(self.admin).patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': True})
        self.assertEqual(r.status_code, 200)
