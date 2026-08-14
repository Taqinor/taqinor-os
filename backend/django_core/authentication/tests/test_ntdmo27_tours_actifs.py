"""NTDMO27 — toggle global ``Company.tours_actifs`` (onglet Paramètres
« Démo & Onboarding »). Additif, défaut True : une société existante n'est
JAMAIS affectée tant qu'elle ne désactive pas explicitement ce réglage.
Distinct de ``mode_presentation_actif`` (NTDMO10) : jamais réservé aux
sociétés démo — toute société peut couper ses visites guidées.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

User = get_user_model()


class ToursActifsDefaultTest(TestCase):
    def test_defaults_true_and_additive(self):
        c = Company.objects.create(nom='Société neuve', slug='co-tours-neuve')
        self.assertTrue(c.tours_actifs)

    def test_toggle_does_not_affect_other_companies(self):
        a = Company.objects.create(nom='A', slug='co-tours-a', tours_actifs=False)
        b = Company.objects.create(nom='B', slug='co-tours-b')
        b.refresh_from_db()
        self.assertFalse(a.tours_actifs)
        self.assertTrue(b.tours_actifs)


class ToursActifsEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Réelle', slug='co-tours-reelle')
        # CompanyViewSet exige IsAdminUser (is_staff), pas seulement un rôle
        # métier — même garde que reset-demo/mode-présentation.
        self.admin = User.objects.create_user(
            'admin-tours', password='x', company=self.company, is_staff=True)

    def _client(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    def test_auth_me_exposes_company_tours_actifs(self):
        r = self._client().get('/api/django/auth/me/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['company_tours_actifs'])

    def test_patch_disables_on_a_real_company_never_a_demo_only_gate(self):
        # Contrairement à mode_presentation_actif, AUCUNE garde « société démo
        # uniquement » : une société réelle peut désactiver directement.
        c = self._client()
        r = c.patch(f'/api/django/companies/{self.company.id}/',
                    {'tours_actifs': False})
        self.assertEqual(r.status_code, 200)
        self.company.refresh_from_db()
        self.assertFalse(self.company.tours_actifs)

    def test_auth_me_reflects_the_toggle(self):
        self.company.tours_actifs = False
        self.company.save(update_fields=['tours_actifs'])
        r = self._client().get('/api/django/auth/me/')
        self.assertFalse(r.data['company_tours_actifs'])
