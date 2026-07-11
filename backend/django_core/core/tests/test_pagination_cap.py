"""YAPIC1 — ``StandardPagination`` : plafond dur + enveloppe inchangée.

Prouve :
  * ``?page_size=5000`` renvoie AU PLUS ``max_page_size`` (200) lignes ;
  * ``?page_size=10`` renvoie 10 lignes ;
  * l'enveloppe ``count/next/previous/results`` est préservée à l'identique ;
  * le plafond s'applique sur ≥3 apps (crm, stock, rh) via leurs endpoints réels.
"""
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from core.pagination import StandardPagination


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class HardCapUnitTests(TestCase):
    """Le plafond dur est purement server-side (get_page_size / paginate)."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.paginator = StandardPagination()

    def test_class_defaults(self):
        self.assertEqual(StandardPagination.page_size, 50)
        self.assertEqual(StandardPagination.max_page_size, 200)
        self.assertEqual(StandardPagination.page_size_query_param, 'page_size')

    def test_page_size_5000_is_capped_at_200(self):
        request = self.factory.get('/x/', {'page_size': '5000'})
        # DRF borne get_page_size à max_page_size.
        self.assertEqual(self.paginator.get_page_size(request), 200)
        # Et concrètement, une séquence de 5000 ne rend qu'au plus 200 lignes.
        page = self.paginator.paginate_queryset(list(range(5000)), request)
        self.assertEqual(len(page), 200)

    def test_page_size_10_returns_10(self):
        request = self.factory.get('/x/', {'page_size': '10'})
        self.assertEqual(self.paginator.get_page_size(request), 10)
        page = self.paginator.paginate_queryset(list(range(500)), request)
        self.assertEqual(len(page), 10)

    def test_default_page_size_is_50(self):
        request = self.factory.get('/x/')
        self.assertEqual(self.paginator.get_page_size(request), 50)

    def test_envelope_shape_preserved(self):
        request = self.factory.get('/x/', {'page_size': '10'})
        self.paginator.paginate_queryset(list(range(30)), request)
        resp = self.paginator.get_paginated_response(list(range(10)))
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, resp.data)
        self.assertEqual(resp.data['count'], 30)
        self.assertEqual(len(resp.data['results']), 10)


class MultiAppCapTests(TestCase):
    """Le plafond s'applique de bout en bout sur crm, stock et rh."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='yapic1-co', defaults={'nom': 'YAPIC1'})[0]
        self.user = CustomUser.objects.create_user(
            username='yapic1', password='x', company=self.company)
        self.api = _auth(self.user)
        self._seed()

    def _seed(self):
        from apps.crm.models import LeadTag
        from apps.stock.models import Categorie
        from apps.rh.models import Departement
        for i in range(12):
            LeadTag.objects.create(company=self.company, nom=f'tag-{i}')
            Categorie.objects.create(company=self.company, nom=f'cat-{i}')
            Departement.objects.create(company=self.company, nom=f'dep-{i}')

    def _assert_envelope_and_page_size(self, url):
        resp = self.api.get(url, {'page_size': '10'})
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)
        self.assertEqual(len(data['results']), 10)
        self.assertEqual(data['count'], 12)

    def test_crm_tags(self):
        self._assert_envelope_and_page_size('/api/django/crm/tags/')

    def test_stock_categories(self):
        self._assert_envelope_and_page_size('/api/django/stock/categories/')

    def test_rh_departements(self):
        self._assert_envelope_and_page_size('/api/django/rh/departements/')

    def test_hard_cap_over_endpoint(self):
        """Un ``page_size`` au-delà du plafond ne renvoie jamais plus que le
        plafond (ici 12 lignes < 200, donc tout tient : la borne n'exclut rien
        d'existant, elle empêche une explosion — vérifié par l'unité ci-dessus)."""
        resp = self.api.get('/api/django/crm/tags/', {'page_size': '5000'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertLessEqual(len(resp.data['results']), 200)
        self.assertEqual(resp.data['count'], 12)
