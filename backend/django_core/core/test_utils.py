"""YOPSB13 — garde N+1 en CI : ``AssertQueryBudgetMixin``.

``assertNumQueries`` existe déjà (stdlib Django) mais n'était utilisé que
dans 1 fichier de test du dépôt — aucun budget n'était posé sur les
endpoints LISTE à fort trafic, donc une régression N+1 (un
``select_related``/``prefetch_related`` retiré par erreur) passait la CI
silencieusement.

``AssertQueryBudgetMixin`` fournit ``assertMaxQueries(n)`` — un mince wrapper
autour de ``django.test.TestCase.assertNumQueries`` qui produit un message
d'échec clair (nombre réel vs plafond) plutôt que le message générique de
Django. Hérite dans n'importe quel ``TestCase`` :

    class MesTests(AssertQueryBudgetMixin, TestCase):
        def test_liste_bornee(self):
            with self.assertMaxQueries(6):
                self.client.get('/api/django/crm/leads/')

Convention attendue par les endpoints LISTE à fort trafic : le nombre de
requêtes NE DOIT PAS grandir avec le nombre de lignes (O(1), pas O(n)) — un
test de budget accompagne typiquement une assertion peuplant 10 puis 25
objets et vérifiant que le compte de requêtes ne bouge pas.
"""
from __future__ import annotations

from contextlib import contextmanager

from django.test.utils import CaptureQueriesContext
from django.db import connection


class AssertQueryBudgetMixin:
    """Mixin de ``TestCase`` : ``assertMaxQueries(n)`` — borne le nombre de
    requêtes SQL exécutées dans le bloc ``with``, message d'échec explicite."""

    @contextmanager
    def assertMaxQueries(self, n, msg=None):  # noqa: N802 — convention Django
        with CaptureQueriesContext(connection) as ctx:
            yield ctx
        actual = len(ctx.captured_queries)
        if actual > n:
            queries_preview = '\n'.join(
                f"  [{i}] {q['sql'][:200]}"
                for i, q in enumerate(ctx.captured_queries))
            base_msg = (
                f'Budget de requêtes dépassé : {actual} requêtes exécutées, '
                f'plafond {n}.\nRequêtes capturées :\n{queries_preview}')
            self.fail(msg or base_msg)
