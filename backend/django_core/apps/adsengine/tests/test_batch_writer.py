"""ADSDEEP33 — Écriture par LOT (Graph ``POST /?batch=``).

Couvre : (a) ``MetaClient.batch_execute`` — encode/décode le lot réel via
``httpx.MockTransport``, respecte la borne 50 opérations, ``error_user_msg``
repris verbatim ; (b) ``services.apply_batch`` — cycle propose→approuve→
applique EN LOT, échec PARTIEL (2/3) laisse 1 et 3 APPLIQUEE et repasse
SEULEMENT 2 en ECHOUEE (journal exact) ; (c) l'invariant PAUSED-only (règle #3)
reste vrai pour l'opération de lot ``pause`` (aucun ``status`` autre que
``PAUSED`` ne peut jamais être écrit par un lot).
"""
import json
from unittest.mock import Mock

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import EngineAction

User = get_user_model()

TOKEN = 'tok-batch'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


class BatchExecuteTests(SimpleTestCase):
    def test_batch_execute_parses_per_operation_results(self):
        def handler(request):
            # Simule 3 sous-réponses : succès / erreur / succès.
            return httpx.Response(200, json=[
                {'code': 200, 'body': json.dumps({'id': 'a1'})},
                {'code': 400, 'body': json.dumps(
                    {'error': {'message': 'Invalid parameter',
                               'error_user_msg': "Le nom est trop long.",
                               'code': 100}})},
                {'code': 200, 'body': json.dumps({'id': 'a3'})},
            ])

        client = make_client(handler)
        results = client.batch_execute([
            {'method': 'POST', 'relative_url': '1', 'body': 'name=A'},
            {'method': 'POST', 'relative_url': '2', 'body': 'name=B'},
            {'method': 'POST', 'relative_url': '3', 'body': 'name=C'},
        ])
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]['success'])
        self.assertEqual(results[0]['body'], {'id': 'a1'})
        self.assertFalse(results[1]['success'])
        # error_user_msg repris VERBATIM (dossier §8).
        self.assertEqual(results[1]['error_user_msg'], "Le nom est trop long.")
        self.assertTrue(results[2]['success'])

    def test_batch_rejects_more_than_50_operations(self):
        client = make_client(lambda r: httpx.Response(200, json=[]))
        ops = [{'method': 'POST', 'relative_url': str(i)} for i in range(51)]
        with self.assertRaises(mc.MetaError):
            client.batch_execute(ops)

    def test_batch_pause_op_forces_paused_only(self):
        client = make_client(lambda r: httpx.Response(200, json=[]))
        op = client.build_batch_op_pause(object_id='123')
        self.assertIn('status=PAUSED', op['body'])
        self.assertNotIn('ACTIVE', op['body'])

    def test_batch_edit_ops_never_send_status(self):
        client = make_client(lambda r: httpx.Response(200, json=[]))
        rename_op = client.build_batch_op_rename(object_id='1', name='X')
        cap_op = client.build_batch_op_spend_cap(campaign_id='2', spend_cap=1000)
        self.assertNotIn('status', rename_op['body'])
        self.assertNotIn('status', cap_op['body'])

    def test_missing_subresponses_marked_failed_not_silently_succeeded(self):
        def handler(request):
            # Graph ne renvoie qu'UNE sous-réponse pour 2 opérations demandées.
            return httpx.Response(200, json=[{'code': 200, 'body': '{}'}])

        client = make_client(handler)
        results = client.batch_execute([
            {'method': 'POST', 'relative_url': '1'},
            {'method': 'POST', 'relative_url': '2'},
        ])
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]['success'])
        self.assertFalse(results[1]['success'])


class ApplyBatchPartialFailureTests(TestCase):
    """ADSDEEP33 — cycle complet propose→approuve→applique EN LOT."""

    def setUp(self):
        self.company = Company.objects.create(nom='Batch Co', slug='batch-co')
        self.user = User.objects.create_user(
            username='approver-batch', password='x', company=self.company)

    def _propose_rename(self, object_id, name):
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.RENAME,
            reason_fr=f"Renommer {object_id}.",
            payload={'object_id': object_id, 'name': name})
        services.approve_action(action, user=self.user)
        return action

    def test_partial_failure_leaves_1_and_3_applied_2_failed(self):
        a1 = self._propose_rename('obj-1', 'Nom 1')
        a2 = self._propose_rename('obj-2', 'Nom 2')
        a3 = self._propose_rename('obj-3', 'Nom 3')

        client = Mock()
        client.build_batch_op_rename.side_effect = lambda object_id, name: {
            'method': 'POST', 'relative_url': object_id,
            'body': f'name={name}'}
        client.batch_execute.return_value = [
            {'success': True, 'body': {'success': True}},
            {'success': False, 'error': {'message': 'bad'},
             'error_user_msg': 'Nom refusé par Meta.'},
            {'success': True, 'body': {'success': True}},
        ]

        result = services.apply_batch([a1, a2, a3], client=client)
        self.assertEqual(len(result), 3)

        a1.refresh_from_db()
        a2.refresh_from_db()
        a3.refresh_from_db()
        self.assertEqual(a1.status, EngineAction.Statut.APPLIQUEE)
        self.assertEqual(a2.status, EngineAction.Statut.ECHOUEE)
        self.assertEqual(a2.error, 'Nom refusé par Meta.')
        self.assertEqual(a3.status, EngineAction.Statut.APPLIQUEE)
        client.batch_execute.assert_called_once()

    def test_apply_batch_refuses_unapproved_action(self):
        proposed_only = services.propose_action(
            self.company, kind=EngineAction.Kind.RENAME,
            reason_fr="Pas encore approuvée.",
            payload={'object_id': 'x', 'name': 'Y'})
        client = Mock()
        with self.assertRaises(services.ActionNotApproved):
            services.apply_batch([proposed_only], client=client)
        client.batch_execute.assert_not_called()

    def test_apply_batch_over_50_raises(self):
        actions = [self._propose_rename(f'obj-{i}', f'N{i}') for i in range(2)]
        # Gonfle artificiellement au-delà de la borne sans reproposer 51 objets.
        with self.assertRaises(ValueError):
            services.apply_batch(actions * 30, client=Mock())

    def test_whole_batch_network_failure_marks_all_failed(self):
        a1 = self._propose_rename('obj-9', 'N9')
        a2 = self._propose_rename('obj-10', 'N10')
        client = Mock()
        client.build_batch_op_rename.side_effect = lambda object_id, name: {
            'method': 'POST', 'relative_url': object_id, 'body': f'name={name}'}
        client.batch_execute.side_effect = mc.MetaError("Panne réseau du lot.")
        services.apply_batch([a1, a2], client=client)
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertEqual(a1.status, EngineAction.Statut.ECHOUEE)
        self.assertEqual(a2.status, EngineAction.Statut.ECHOUEE)
