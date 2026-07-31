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
from django.db import connection, connections

# Plafond accordé au TRUNCATE de purge des fixtures (cf.
# ``WideTeardownTimeoutMixin``). Généreux (10× le coût mesuré) mais FINI : une
# purge réellement bloquée doit finir par échouer, jamais figer la suite.
FIXTURE_TEARDOWN_TIMEOUT_MS = 300_000


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


class WideTeardownTimeoutMixin:
    """Mixin de ``TransactionTestCase`` : la purge de fin de test échappe au
    ``statement_timeout`` de PRODUCTION.

    ``TransactionTestCase._fixture_teardown()`` lance un ``flush`` = UN SEUL
    ``TRUNCATE`` couvrant tout le schéma (et ``available_apps`` n'y change
    rien : Django passe alors ``allow_cascade=True``, et le ``CASCADE`` depuis
    ``authentication_company`` ratisse de toute façon les ~900 tables du
    dépôt). Son coût suit le SCHÉMA, pas les données — mesuré 16 à 31 s par
    test sur un runner CI. Or NTPLT18 pose un ``statement_timeout`` de 30 s sur
    CHAQUE connexion (``settings.DATABASES['default']['OPTIONS']``) : les
    purges qui franchissent 30 s sont annulées (« canceling statement due to
    statement timeout »), les tables restent PLEINES, et le test suivant de la
    classe explose en doublon de clé (société/utilisateur déjà créé) — une
    cascade d'ERROR sans le moindre rapport avec le code testé, qui empire à
    chaque table ajoutée au dépôt.

    Ce garde-fou existe pour empêcher une requête ORM folle d'épingler un
    worker gunicorn ; la purge de fixtures du runner de tests n'en est pas une
    (même raisonnement que l'exemption déjà documentée des dumps
    ``pg_dump``/``pg_restore``, hors OPTIONS car lancés en subprocess). On
    l'élargit donc UNIQUEMENT le temps de ce TRUNCATE, puis on rétablit la
    valeur d'origine : aucun autre statement du test n'est exempté, et le
    réglage de production n'est pas touché.

    Usage — le mixin passe AVANT la classe de base :

        class MesTests(WideTeardownTimeoutMixin, TransactionTestCase):
            ...
    """

    def _fixture_teardown(self):  # noqa: N802 — nom imposé par Django
        previous = {}
        for alias in self._databases_names(include_mirrors=False):
            conn = connections[alias]
            if conn.vendor != 'postgresql':
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute('SHOW statement_timeout')
                    previous[alias] = cur.fetchone()[0]
                    cur.execute(
                        f'SET statement_timeout = {FIXTURE_TEARDOWN_TIMEOUT_MS}')
            except Exception:  # pragma: no cover - jamais casser un teardown
                previous.pop(alias, None)
        try:
            super()._fixture_teardown()
        finally:
            for alias, value in previous.items():
                try:
                    with connections[alias].cursor() as cur:
                        # psycopg2 interpole côté client : `SET` n'accepte pas
                        # de paramètre lié, mais la valeur reste échappée.
                        cur.execute('SET statement_timeout = %s', [value])
                except Exception:  # pragma: no cover - connexion déjà fermée
                    pass
