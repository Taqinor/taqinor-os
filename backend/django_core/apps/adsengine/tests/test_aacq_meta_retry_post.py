"""AACQ17 — Plus aucun POST rejoué automatiquement vers Meta quand la première
réponse se perd (``ReadTimeout`` / 5xx) : exactement UN POST, ``MetaError`` en
français « réponse perdue — vérifier dans Meta avant de relancer ». Les GET
restent rejoués. Vrai ``MetaClient`` en transport simulé (aucun appel réel).
"""
import httpx
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import services
from apps.adsengine.meta_client import MetaClient, MetaError
from apps.adsengine.models import EngineAction


def _client(sequence, calls):
    """Transport qui rejoue ``sequence`` (exception ou réponse) puis 200."""
    seq = list(sequence)

    def handler(request):
        calls.append(request)
        item = seq.pop(0) if seq else httpx.Response(200, json={'id': '92'})
        if isinstance(item, Exception):
            raise item
        return item
    return MetaClient(
        access_token='tok', ad_account_id='act_1', page_id='page-1',
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=3, backoff_base=0)


ECRITURES = {
    'create_adset': lambda c: c.create_adset(name='AS', campaign_id='1'),
    'create_page_post': lambda c: c.create_page_post(
        message='Bonjour', published=True),
    'reply_to_comment': lambda c: c.reply_to_comment(
        comment_id='cm-1', message='Merci'),
    'batch_execute': lambda c: c.batch_execute(
        [c.build_batch_op_rename(object_id='1', name='N')]),
}
PANNES = {
    'read_timeout': lambda: httpx.ReadTimeout('perdu'),
    '503': lambda: httpx.Response(503, json={'error': {'message': 'down'}}),
}


class RetryPostTests(SimpleTestCase):
    def test_chaque_ecriture_un_seul_post(self):
        for nom, appel in ECRITURES.items():
            for panne, fabrique in PANNES.items():
                with self.subTest(methode=nom, panne=panne):
                    calls = []
                    client = _client([fabrique()], calls)
                    with self.assertRaises(MetaError) as ctx:
                        appel(client)
                    self.assertEqual(
                        [r.method for r in calls], ['POST'])
                    self.assertIn('vérifier dans Meta avant de relancer',
                                  str(ctx.exception))

    def test_get_insights_rejoue(self):
        for panne, fabrique in PANNES.items():
            with self.subTest(panne=panne):
                calls = []
                seq = [fabrique(), httpx.Response(200, json={'data': [
                    {'spend': '1.00'}]})]
                client = _client(seq, calls)
                data = client.get_insights('act_1')
                self.assertEqual(len(calls), 2)
                self.assertEqual(data, [{'spend': '1.00'}])

    def test_rapport_asynchrone_en_liste_blanche(self):
        calls = []
        client = _client([httpx.ReadTimeout('perdu')], calls)
        payload = client._request('POST', 'act_1/insights', data={})
        self.assertEqual(len(calls), 2)
        self.assertEqual(payload, {'id': '92'})


class ActionEchoueeTests(TestCase):
    def test_action_echouee_avec_le_message(self):
        company = Company.objects.create(nom='Retry', slug='aacq17-retry')
        action = EngineAction.objects.create(
            company=company, kind=EngineAction.Kind.RENAME,
            reason_fr='Renommer.', status=EngineAction.Statut.APPROUVEE,
            payload={'object_id': '120', 'name': 'Nouveau'})
        calls = []
        with self.assertRaises(MetaError):
            services.apply_action(
                action, client=_client([httpx.ReadTimeout('perdu')], calls))
        self.assertEqual(len(calls), 1)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
        self.assertIn('vérifier dans Meta avant de relancer', action.error)
