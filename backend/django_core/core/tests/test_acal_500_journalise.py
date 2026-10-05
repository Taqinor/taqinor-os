"""ACAL315 — un 500 du gestionnaire d'exceptions unique n'est JAMAIS muet.

Constat live (audit PUB) : « django_core logs gave no Python traceback for
the 500s ; request_id null in the shell » — la base non migrée
(ProgrammingError) est restée invisible. Ici, une VRAIE vue DRF lève une
exception non gérée et passe par le VRAI ``taqinor_exception_handler``
(REST_FRAMEWORK['EXCEPTION_HANDLER']) — aucun mock du handler.
"""
from django.db import ProgrammingError
from django.test import RequestFactory, SimpleTestCase
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.middleware import RequestIdMiddleware


class _VueQuiCasse(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        raise ProgrammingError('relation "x" does not exist')


class Acal500JournaliseTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.vue = _VueQuiCasse.as_view()

    def test_exception_non_geree_journalise_la_pile(self):
        requete = self.factory.get('/api/django/test/acal315/')
        with self.assertLogs('core.exceptions', level='ERROR') as journal:
            reponse = self.vue(requete)
        self.assertEqual(reponse.status_code, 500)
        self.assertEqual(reponse.data['error']['code'], 'server_error')
        request_id = reponse.data['error']['request_id']
        self.assertEqual(len(journal.records), 1)
        record = journal.records[0]
        # La pile est là (exc_info) et c'est bien l'exception levée.
        self.assertIsNotNone(record.exc_info)
        self.assertIs(record.exc_info[0], ProgrammingError)
        # Le request_id de la réponse est celui du journal.
        self.assertEqual(record.request_id, request_id)
        self.assertIn(request_id, record.getMessage())
        self.assertEqual(record.path, '/api/django/test/acal315/')
        self.assertEqual(record.method, 'GET')
        # Le message générique ne fuite jamais le détail interne au client.
        self.assertNotIn('relation', reponse.data['error']['message'])

    def test_request_id_jamais_null(self):
        # 1) Sans middleware (shell, requête construite à la main).
        requete = self.factory.get('/api/django/test/acal315/')
        with self.assertLogs('core.exceptions', level='ERROR'):
            reponse = self.vue(requete)
        request_id = reponse.data['error']['request_id']
        self.assertIsInstance(request_id, str)
        self.assertTrue(request_id)
        self.assertEqual(reponse['X-Request-ID'], request_id)

        # 2) Avec le middleware de corrélation, sans en-tête entrant.
        pile = RequestIdMiddleware(self.vue)
        requete = self.factory.get('/api/django/test/acal315/')
        with self.assertLogs('core.exceptions', level='ERROR') as journal:
            reponse = pile(requete)
        request_id = reponse.data['error']['request_id']
        self.assertIsInstance(request_id, str)
        self.assertTrue(request_id)
        self.assertEqual(reponse['X-Request-ID'], request_id)
        self.assertEqual(journal.records[0].request_id, request_id)
