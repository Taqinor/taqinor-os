"""Tests de l'agrégation feedback par thème (NTIDE38).

Couvre : ``selectors.feedback_by_theme`` (total/non-lus/citations par
thème, thèmes sans feedback omis) et l'endpoint
``GET /api/django/innovation/feedback-resume`` (palier admin uniquement)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
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


class FeedbackByThemeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide38-a', 'A')
        self.user = make_user(self.co_a, 'ntide38-user')

    def test_counts_total_and_non_lus_per_theme(self):
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Bug 1',
            theme=FeedbackProduit.Theme.BUG)
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Bug 2',
            theme=FeedbackProduit.Theme.BUG, statut=FeedbackProduit.Statut.LU)
        resume = selectors.feedback_by_theme(self.co_a)
        bug = next(r for r in resume if r['theme'] == 'bug')
        self.assertEqual(bug['total'], 2)
        self.assertEqual(bug['non_lus'], 1)
        self.assertIn('Bug 1', bug['exemples'])

    def test_theme_without_feedback_omitted(self):
        resume = selectors.feedback_by_theme(self.co_a)
        self.assertEqual(resume, [])

    def test_examples_capped_at_three(self):
        for i in range(5):
            FeedbackProduit.objects.create(
                company=self.co_a, auteur=self.user, titre=f'UX {i}',
                theme=FeedbackProduit.Theme.UX)
        resume = selectors.feedback_by_theme(self.co_a)
        ux = next(r for r in resume if r['theme'] == 'ux')
        self.assertEqual(ux['total'], 5)
        self.assertEqual(len(ux['exemples']), 3)


class FeedbackResumeEndpointTests(TestCase):
    BASE = '/api/django/innovation/feedback-resume/'

    def setUp(self):
        self.co_a = make_company('innov-ntide38-api-a', 'A')
        self.admin = make_user(self.co_a, 'ntide38-api-admin', role_legacy='admin')
        self.normal = make_user(self.co_a, 'ntide38-api-normal')

    def test_admin_can_view(self):
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Retour',
            theme=FeedbackProduit.Theme.PERFORMANCE)
        resp = auth(self.admin).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)

    def test_normal_role_refused(self):
        resp = auth(self.normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
