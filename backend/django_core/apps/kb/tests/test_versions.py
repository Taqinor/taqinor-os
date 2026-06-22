"""Tests KB2 — versionnage des articles + transitions de statut.

Couvre : action ``publier`` (statut→publie + instantané), action
``nouvelle-version`` (instantané sans changer le statut), snapshot automatique
à la mise à jour de l'article, numérotation incrémentale par article
(max(version)+1), isolation entre sociétés sur l'historique des versions et
404 cross-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb.models import KbArticle, KbArticleVersion

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class KbVersionTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'
    VERSIONS = '/api/django/kb/versions/'

    def setUp(self):
        self.co_a = make_company('kbv-a', 'A')
        self.co_b = make_company('kbv-b', 'B')
        self.user_a = make_user(self.co_a, 'kbv-a')
        self.user_b = make_user(self.co_b, 'kbv-b')

    def _article(self, company, **kw):
        defaults = {'titre': 'Procédure', 'corps': 'v1'}
        defaults.update(kw)
        return KbArticle.objects.create(company=company, **defaults)

    # --- statut / publier -------------------------------------------------
    def test_publier_flips_statut_and_snapshots(self):
        art = self._article(self.co_a)
        self.assertEqual(art.statut, KbArticle.Statut.BROUILLON)
        api = auth(self.user_a)
        resp = api.post(f'{self.ARTICLES}{art.id}/publier/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], KbArticle.Statut.PUBLIE)
        art.refresh_from_db()
        self.assertEqual(art.statut, KbArticle.Statut.PUBLIE)
        versions = KbArticleVersion.objects.filter(article=art)
        self.assertEqual(versions.count(), 1)
        v = versions.first()
        self.assertEqual(v.version, 1)
        self.assertEqual(v.company, self.co_a)
        self.assertEqual(v.auteur, self.user_a)
        self.assertEqual(v.titre, 'Procédure')
        self.assertEqual(v.contenu, 'v1')

    def test_nouvelle_version_snapshots_without_status_change(self):
        art = self._article(self.co_a, statut=KbArticle.Statut.BROUILLON)
        api = auth(self.user_a)
        resp = api.post(
            f'{self.ARTICLES}{art.id}/nouvelle-version/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['version'], 1)
        art.refresh_from_db()
        self.assertEqual(art.statut, KbArticle.Statut.BROUILLON)
        self.assertEqual(KbArticleVersion.objects.filter(article=art).count(), 1)

    # --- snapshot on update + incremental numero --------------------------
    def test_update_creates_incremental_versions(self):
        art = self._article(self.co_a)
        api = auth(self.user_a)
        r1 = api.patch(
            f'{self.ARTICLES}{art.id}/', {'corps': 'v2'}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = api.patch(
            f'{self.ARTICLES}{art.id}/', {'corps': 'v3'}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        nums = list(KbArticleVersion.objects
                    .filter(article=art)
                    .order_by('version')
                    .values_list('version', flat=True))
        self.assertEqual(nums, [1, 2])
        latest = KbArticleVersion.objects.filter(article=art).order_by('-version').first()
        self.assertEqual(latest.contenu, 'v3')

    def test_version_numbers_are_per_article(self):
        a1 = self._article(self.co_a, titre='A1')
        a2 = self._article(self.co_a, titre='A2')
        api = auth(self.user_a)
        api.post(f'{self.ARTICLES}{a1.id}/nouvelle-version/', {}, format='json')
        api.post(f'{self.ARTICLES}{a1.id}/nouvelle-version/', {}, format='json')
        api.post(f'{self.ARTICLES}{a2.id}/nouvelle-version/', {}, format='json')
        self.assertEqual(
            sorted(KbArticleVersion.objects.filter(article=a1)
                   .values_list('version', flat=True)),
            [1, 2])
        self.assertEqual(
            list(KbArticleVersion.objects.filter(article=a2)
                 .values_list('version', flat=True)),
            [1])

    # --- company scoping --------------------------------------------------
    def test_version_list_isolation(self):
        art_a = self._article(self.co_a)
        KbArticleVersion.objects.create(
            company=self.co_a, article=art_a, version=1,
            titre=art_a.titre, contenu=art_a.corps)
        resp = auth(self.user_b).get(self.VERSIONS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_cross_tenant_publier_404(self):
        art_a = self._article(self.co_a)
        resp = auth(self.user_b).post(
            f'{self.ARTICLES}{art_a.id}/publier/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
        # no version leaked into B's tenant or A's article
        self.assertEqual(KbArticleVersion.objects.filter(article=art_a).count(), 0)

    def test_cross_tenant_version_retrieve_404(self):
        art_a = self._article(self.co_a)
        v = KbArticleVersion.objects.create(
            company=self.co_a, article=art_a, version=1,
            titre=art_a.titre, contenu=art_a.corps)
        resp = auth(self.user_b).get(f'{self.VERSIONS}{v.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse_versions(self):
        normal = make_user(self.co_a, 'kbv-normal', role='normal')
        resp = auth(normal).get(self.VERSIONS)
        self.assertEqual(resp.status_code, 403)
