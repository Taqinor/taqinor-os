"""ADSDEEP34 — A/B test NATIF Meta (``ad_studies`` SPLIT_TEST_V2, dossier §7).

Couvre : validation de forme (2-5 cellules, treatment_percentage >= 10 %, somme
100) côté client ET côté service (fail-fast, jamais un rejet Graph tardif),
aucun ``status`` envoyé (une étude n'en porte pas), l'avertissement
d'immutabilité porté dans ``payload['warnings']`` dès la proposition, le cycle
propose→approuve→applique, et la lecture des résultats dans un ``DecisionLog``.
"""
from unittest.mock import Mock

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import DecisionLog, EngineAction, Experiment

User = get_user_model()

TOKEN = 'tok-study'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


CELLS_3 = [
    {'name': 'Contrôle', 'treatment_percentage': 40, 'ads': ['ad-1']},
    {'name': 'Variante A', 'treatment_percentage': 30, 'ads': ['ad-2']},
    {'name': 'Variante B', 'treatment_percentage': 30, 'ads': ['ad-3']},
]


class MetaClientAdStudyTests(SimpleTestCase):
    def test_create_ad_study_happy_path(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'study-1'})

        client = make_client(handler)
        result = client.create_ad_study(name='Test hook', cells=CELLS_3)
        self.assertEqual(result, {'id': 'study-1'})
        body = captured['request'].content.decode('utf-8')
        self.assertIn('SPLIT_TEST_V2', body)
        # Aucun statut envoyé — une étude n'en porte pas (invariant règle #3).
        self.assertNotIn('status', body)

    def test_rejects_fewer_than_2_cells(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        with self.assertRaises(mc.MetaError):
            client.create_ad_study(name='X', cells=[CELLS_3[0]])

    def test_rejects_more_than_5_cells(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        six = [dict(c, name=f'C{i}') for i, c in
               enumerate([CELLS_3[0]] * 6)]
        for c in six:
            c['treatment_percentage'] = 100 / 6
        with self.assertRaises(mc.MetaError):
            client.create_ad_study(name='X', cells=six)

    def test_rejects_treatment_below_10_percent(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        cells = [
            {'name': 'A', 'treatment_percentage': 5},
            {'name': 'B', 'treatment_percentage': 95},
        ]
        with self.assertRaises(mc.MetaError):
            client.create_ad_study(name='X', cells=cells)

    def test_rejects_percentages_not_summing_to_100(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        cells = [
            {'name': 'A', 'treatment_percentage': 40},
            {'name': 'B', 'treatment_percentage': 40},
        ]
        with self.assertRaises(mc.MetaError):
            client.create_ad_study(name='X', cells=cells)

    def test_get_ad_study_results_reads_results_field(self):
        def handler(request):
            self.assertIn('results', request.url.params.get('fields', ''))
            return httpx.Response(200, json={
                'id': 'study-1', 'results': {'winner': 'ad-2'}})

        client = make_client(handler)
        payload = client.get_ad_study_results('study-1')
        self.assertEqual(payload['results'], {'winner': 'ad-2'})


class ProposeAdStudyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Study Co', slug='study-co')
        self.user = User.objects.create_user(
            username='study-approver', password='x', company=self.company)

    def test_propose_ad_study_carries_immutability_warning(self):
        action = services.propose_ad_study(
            self.company, name='Hook fatigue test', cells=CELLS_3)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertIn(services.WARN_AD_STUDY_IMMUTABLE, action.payload['warnings'])
        self.assertEqual(action.kind, services.KIND_CREATE_AD_STUDY)

    def test_propose_ad_study_rejects_invalid_shape_before_creating_action(self):
        with self.assertRaises(ValueError):
            services.propose_ad_study(
                self.company, name='X',
                cells=[{'name': 'A', 'treatment_percentage': 100}])
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_full_cycle_reaches_client_paused_compatible(self):
        action = services.propose_ad_study(
            self.company, name='Cycle test', cells=CELLS_3)
        services.approve_action(action, user=self.user)
        client = Mock()
        client.create_ad_study.return_value = {'id': 'study-9'}
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        client.create_ad_study.assert_called_once_with(
            name='Cycle test', cells=CELLS_3, extra_fields=None)
        self.assertEqual(action.result, {'id': 'study-9'})


class SyncAdStudyResultsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sync Co', slug='sync-co')

    def test_sync_writes_decision_log(self):
        experiment = Experiment.objects.create(
            company=self.company, name='Exp A', meta_study_id='study-42')
        client = Mock()
        client.get_ad_study_results.return_value = {
            'id': 'study-42', 'cells': CELLS_3,
            'results': {'winner': 'ad-2', 'confidence': 0.94}}
        log = services.sync_ad_study_results(experiment, client=client)
        self.assertIsInstance(log, DecisionLog)
        self.assertEqual(log.experiment_id, experiment.pk)
        self.assertEqual(log.posteriors, {'winner': 'ad-2', 'confidence': 0.94})
        client.get_ad_study_results.assert_called_once_with('study-42')

    def test_sync_is_noop_without_study_id(self):
        experiment = Experiment.objects.create(company=self.company, name='Exp B')
        client = Mock()
        result = services.sync_ad_study_results(experiment, client=client)
        self.assertIsNone(result)
        client.get_ad_study_results.assert_not_called()
