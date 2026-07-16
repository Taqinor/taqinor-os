"""ENGFIX5 — L'action PAUSE est exécutable, et la pause reste PAUSED-only.

``EngineAction.Kind.PAUSE`` est proposée par le détecteur d'anomalie (ENG9) et
le brief hebdo (ENG11), mais ``_dispatch`` n'avait aucune branche PAUSE : une
pause approuvée levait « non routable » et atterrissait ECHOUEE — le moteur ne
pouvait pas exécuter sa propre action de sécurité. On prouve ici :
  (a) meta_client — ``update_status_paused`` envoie ``status=PAUSED`` et n'accepte
      AUCUN kwarg ``status`` (TypeError), comme les créations ;
  (b) services — une PAUSE approuvée dispatche et atterrit APPLIQUEE.

L'invariant permanent (règle #3) est préservé : aucune méthode ne peut activer.
"""
from unittest.mock import Mock
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import EngineAction

TOKEN = 'tok-pause-1'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


class UpdateStatusPausedTests(SimpleTestCase):
    def test_update_status_paused_sends_paused(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        client = make_client(handler)
        result = client.update_status_paused(object_id='123', level='campaign')
        self.assertEqual(result, {'success': True})
        req = captured['request']
        form = parse_qs(req.content.decode('utf-8'))
        self.assertEqual(form['status'], ['PAUSED'])
        # La cible est dans le chemin (node id), jamais un statut ACTIVE.
        self.assertTrue(str(req.url).endswith('/123'))
        self.assertNotIn('ACTIVE', req.content.decode('utf-8'))

    def test_no_status_kwarg_accepted(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        # Comme les créations : aucun status paramétrable → le langage lève.
        with self.assertRaises(TypeError):
            client.update_status_paused(object_id='1', status='ACTIVE')

    def test_level_does_not_influence_status(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={})

        client = make_client(handler)
        # Quel que soit ``level``, le statut posé reste PAUSED.
        client.update_status_paused(object_id='9', level='ad')
        form = parse_qs(captured['request'].content.decode('utf-8'))
        self.assertEqual(form['status'], ['PAUSED'])


class PauseDispatchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pause Co', slug='pause-co')

    def test_approved_pause_dispatches_and_applies(self):
        action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr="Mettre en pause campaign c1 : dépense sans résultat.",
            payload={'target_type': 'campaign', 'target_meta_id': 'c1',
                     'target_object_id': 42},
            status=EngineAction.Statut.APPROUVEE)
        client = Mock()
        client.update_status_paused.return_value = {'success': True}
        services.apply_action(action, client=client)
        client.update_status_paused.assert_called_once_with(
            object_id='c1', level='campaign')
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertEqual(action.result, {'success': True})
