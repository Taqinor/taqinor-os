"""Tests du hotspot feedback (NTIDE46).

Couvre : ``selectors.hotspot_feedback`` (pages ayant reçu au moins 10
feedbacks sur les 7 derniers jours, feedbacks sans page/anciens ignorés) et
l'endpoint ``GET /api/django/innovation/feedback-hotspot`` (palier admin)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class HotspotFeedbackSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide46-a', 'A')
        self.user = make_user(self.co_a, 'ntide46-user')

    def _create(self, source_page, created_at=None):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Retour',
            source_page=source_page)
        if created_at is not None:
            FeedbackProduit.objects.filter(pk=fb.pk).update(
                created_at=created_at)
        return fb

    def test_page_below_threshold_omitted(self):
        for _ in range(9):
            self._create('/chantiers/détail')
        self.assertEqual(selectors.hotspot_feedback(self.co_a), [])

    def test_page_at_threshold_included(self):
        for _ in range(10):
            self._create('/chantiers/détail')
        result = selectors.hotspot_feedback(self.co_a)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['source_page'], '/chantiers/détail')
        self.assertEqual(result[0]['nombre'], 10)

    def test_blank_source_page_ignored(self):
        for _ in range(15):
            self._create('')
        self.assertEqual(selectors.hotspot_feedback(self.co_a), [])

    def test_old_feedback_excluded(self):
        ancien = timezone.now() - timedelta(days=10)
        for _ in range(10):
            self._create('/ventes/devis', created_at=ancien)
        self.assertEqual(selectors.hotspot_feedback(self.co_a), [])

    def test_ordered_by_count_desc(self):
        for _ in range(12):
            self._create('/crm/leads')
        for _ in range(10):
            self._create('/stock/produits')
        result = selectors.hotspot_feedback(self.co_a)
        self.assertEqual(
            [r['source_page'] for r in result], ['/crm/leads', '/stock/produits'])


class HotspotFeedbackEndpointTests(TestCase):
    BASE = '/api/django/innovation/feedback-hotspot/'

    def setUp(self):
        self.co_a = make_company('innov-ntide46-ep-a', 'A')
        self.admin = make_user(self.co_a, 'ntide46-ep-admin', role_legacy='admin')
        self.normal = make_user(self.co_a, 'ntide46-ep-normal')

    def test_admin_can_view(self):
        for _ in range(10):
            FeedbackProduit.objects.create(
                company=self.co_a, auteur=self.normal, titre='Retour',
                source_page='/sav/tickets')
        resp = auth(self.admin).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)

    def test_normal_role_refused(self):
        resp = auth(self.normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
