"""YAPIC1 — ``StandardPagination`` : plafond dur + enveloppe inchangée.

Prouve :
  * ``?page_size=5000`` renvoie AU PLUS ``max_page_size`` (200) lignes ;
  * ``?page_size=10`` renvoie 10 lignes ;
  * l'enveloppe ``count/next/previous/results`` est préservée à l'identique.

NB : ``core`` est une couche fondation (contrat import-linter
``core-foundation-is-a-base-layer``) — elle ne doit JAMAIS importer une app
métier (crm/stock/rh…). Le comportement de la classe est donc prouvé ici en
UNITÉ pure (aucun endpoint réel, aucun modèle métier importé) ; le câblage
`DEFAULT_PAGINATION_CLASS` est porté par `settings/base.py` et couvert de bout
en bout par les suites des apps elles-mêmes.
"""
from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.pagination import StandardPagination


class HardCapUnitTests(SimpleTestCase):
    """Le plafond dur est purement server-side (get_page_size / paginate)."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.paginator = StandardPagination()

    def _req(self, params=None):
        # DRF pagination lit request.query_params → il faut une Request DRF,
        # pas la WSGIRequest brute d'APIRequestFactory (qui n'a que .GET).
        return Request(self.factory.get('/x/', params or {}))

    def test_class_defaults(self):
        self.assertEqual(StandardPagination.page_size, 50)
        self.assertEqual(StandardPagination.max_page_size, 200)
        self.assertEqual(StandardPagination.page_size_query_param, 'page_size')

    def test_page_size_5000_is_capped_at_200(self):
        request = self._req({'page_size': '5000'})
        # DRF borne get_page_size à max_page_size.
        self.assertEqual(self.paginator.get_page_size(request), 200)
        # Et concrètement, une séquence de 5000 ne rend qu'au plus 200 lignes.
        page = self.paginator.paginate_queryset(list(range(5000)), request)
        self.assertEqual(len(page), 200)

    def test_page_size_10_returns_10(self):
        request = self._req({'page_size': '10'})
        self.assertEqual(self.paginator.get_page_size(request), 10)
        page = self.paginator.paginate_queryset(list(range(500)), request)
        self.assertEqual(len(page), 10)

    def test_default_page_size_is_50(self):
        request = self._req()
        self.assertEqual(self.paginator.get_page_size(request), 50)

    def test_envelope_shape_preserved(self):
        request = self._req({'page_size': '10'})
        self.paginator.paginate_queryset(list(range(30)), request)
        resp = self.paginator.get_paginated_response(list(range(10)))
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, resp.data)
        self.assertEqual(resp.data['count'], 30)
        self.assertEqual(len(resp.data['results']), 10)
