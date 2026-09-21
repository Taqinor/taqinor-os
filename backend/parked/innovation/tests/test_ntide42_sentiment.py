"""Tests du sentiment optionnel sur le feedback produit (NTIDE42).

Couvre : le champ ``FeedbackProduit.sentiment`` (vide par défaut, écrit à
la création par l'auteur) et son agrégation dans
``selectors.feedback_by_theme`` (NTIDE38)."""
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


class SentimentModelTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide42-a', 'A')
        self.user = make_user(self.co_a, 'ntide42-user')

    def test_sentiment_blank_by_default(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Sans sentiment')
        self.assertEqual(fb.sentiment, '')

    def test_sentiment_accepts_choices(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Content',
            sentiment=FeedbackProduit.Sentiment.POSITIF)
        self.assertEqual(fb.sentiment, 'positif')


class SentimentCreateEndpointTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide42-ep-a', 'A')
        self.normal = make_user(self.co_a, 'ntide42-ep-normal')

    def test_sentiment_writable_at_creation(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Le bouton export est trop petit',
            'sentiment': 'negatif',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.sentiment, 'negatif')

    def test_sentiment_optional(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Un retour sans sentiment',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.sentiment, '')


class FeedbackByThemeSentimentTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide42-agg-a', 'A')
        self.user = make_user(self.co_a, 'ntide42-agg-user')

    def test_par_sentiment_counts(self):
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Bug 1',
            theme=FeedbackProduit.Theme.BUG, sentiment='negatif')
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Bug 2',
            theme=FeedbackProduit.Theme.BUG, sentiment='negatif')
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Bug 3',
            theme=FeedbackProduit.Theme.BUG)
        resume = selectors.feedback_by_theme(self.co_a)
        bug = next(r for r in resume if r['theme'] == 'bug')
        self.assertEqual(bug['par_sentiment']['negatif'], 2)
        self.assertEqual(bug['par_sentiment']['non_renseigne'], 1)
        self.assertNotIn('positif', bug['par_sentiment'])

    def test_par_sentiment_omitted_when_all_blank(self):
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='UX 1',
            theme=FeedbackProduit.Theme.UX)
        resume = selectors.feedback_by_theme(self.co_a)
        ux = next(r for r in resume if r['theme'] == 'ux')
        self.assertEqual(ux['par_sentiment'], {'non_renseigne': 1})
