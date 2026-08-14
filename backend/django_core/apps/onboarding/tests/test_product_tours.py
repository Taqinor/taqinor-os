"""NTDMO14/16 — catalogue des visites guidées (product tours) + endpoint."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.onboarding.models import ProductTourStep, TourProgress
from apps.onboarding.services import (
    marquer_tour_vu, reinitialiser_tour, seed_default_tour_steps,
)
from apps.roles.models import Role

User = get_user_model()

# NTDMO14 — les 6 écrans money-path ciblés par le catalogue.
EXPECTED_TOURS = {'devis', 'leads', 'factures', 'chantiers', 'stock', 'dashboard'}


class ProductTourCatalogueTest(TestCase):
    """Le catalogue est seedé par migration (0005) — pas de requête réseau
    bloquante nécessaire pour le charger."""

    def test_catalogue_has_six_tours(self):
        tours = set(ProductTourStep.objects.values_list('tour_key', flat=True))
        self.assertEqual(tours, EXPECTED_TOURS)

    def test_each_tour_has_ordered_steps(self):
        for tour_key in EXPECTED_TOURS:
            steps = list(
                ProductTourStep.objects.filter(tour_key=tour_key)
                .order_by('ordre'))
            self.assertGreater(len(steps), 0)
            ordres = [s.ordre for s in steps]
            self.assertEqual(ordres, sorted(ordres))

    def test_seed_is_idempotent(self):
        before = ProductTourStep.objects.count()
        seed_default_tour_steps()
        seed_default_tour_steps()
        self.assertEqual(ProductTourStep.objects.count(), before)


class ProductTourEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co', slug='co-pt')
        self.role_admin = Role.objects.create(
            company=self.company, nom='Administrateur')
        self.u1 = User.objects.create_user(
            'ptu1', password='x', company=self.company, role=self.role_admin)
        self.u2 = User.objects.create_user(
            'ptu2', password='x', company=self.company, role=self.role_admin)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_list_returns_all_tours_with_steps_and_statuses(self):
        r = self._client(self.u1).get('/api/django/onboarding/tours/')
        self.assertEqual(r.status_code, 200)
        keys = {t['tour_key'] for t in r.data}
        self.assertEqual(keys, EXPECTED_TOURS)
        for t in r.data:
            self.assertIn('etapes', t)
            self.assertGreater(len(t['etapes']), 0)
            self.assertFalse(t['vu'])

    def test_marking_a_tour_seen_persists_and_never_reappears(self):
        c = self._client(self.u1)
        r = c.post('/api/django/onboarding/tours/devis/vu/')
        self.assertEqual(r.status_code, 200)
        devis = next(t for t in r.data if t['tour_key'] == 'devis')
        self.assertTrue(devis['vu'])
        # Un nouveau chargement confirme la persistance (pas de re-déclenchement).
        r2 = c.get('/api/django/onboarding/tours/')
        devis2 = next(t for t in r2.data if t['tour_key'] == 'devis')
        self.assertTrue(devis2['vu'])

    def test_seen_status_is_per_user(self):
        marquer_tour_vu(self.company, self.u1, 'leads')
        r1 = self._client(self.u1).get('/api/django/onboarding/tours/')
        r2 = self._client(self.u2).get('/api/django/onboarding/tours/')
        leads1 = next(t for t in r1.data if t['tour_key'] == 'leads')
        leads2 = next(t for t in r2.data if t['tour_key'] == 'leads')
        self.assertTrue(leads1['vu'])
        self.assertFalse(leads2['vu'])

    def test_marquer_vu_is_idempotent(self):
        marquer_tour_vu(self.company, self.u1, 'stock')
        first = TourProgress.objects.get(user=self.u1, tour_key='stock').vu_le
        marquer_tour_vu(self.company, self.u1, 'stock')
        second = TourProgress.objects.get(user=self.u1, tour_key='stock').vu_le
        self.assertEqual(first, second)

    # ── NTDMO16 — bouton « Revoir » ─────────────────────────────────────────
    def test_revoir_resets_tour_for_this_user_only(self):
        marquer_tour_vu(self.company, self.u1, 'chantiers')
        marquer_tour_vu(self.company, self.u2, 'chantiers')
        c = self._client(self.u1)
        r = c.post('/api/django/onboarding/tours/chantiers/revoir/')
        self.assertEqual(r.status_code, 200)
        chantiers1 = next(t for t in r.data if t['tour_key'] == 'chantiers')
        self.assertFalse(chantiers1['vu'])
        r2 = self._client(self.u2).get('/api/django/onboarding/tours/')
        chantiers2 = next(t for t in r2.data if t['tour_key'] == 'chantiers')
        self.assertTrue(chantiers2['vu'])

    def test_reinitialiser_tour_service_is_idempotent(self):
        reinitialiser_tour(self.company, self.u1, 'dashboard')
        reinitialiser_tour(self.company, self.u1, 'dashboard')
        self.assertFalse(
            TourProgress.objects.filter(
                user=self.u1, tour_key='dashboard', vu_le__isnull=False)
            .exists())
