"""Tests YOPSB10 — registre de rétention partagé + sweep unifié.

Couvre : une politique factice enregistrée est exécutée par
``run_all_policies``, dry-run ne supprime rien (compte transmis tel quel,
mais ``apply_=False`` est bien reçu par la politique), ``apply_=True``
exécute réellement, chaque exécution est journalisée en ``RetentionRun``,
une politique en échec n'arrête pas les autres, la commande de gestion
fonctionne dans les deux modes."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from core import retention
from core.models import RetentionRun


class RetentionRegistryTests(TestCase):
    def setUp(self):
        # QX42 — des apps (ex. crm) enregistrent désormais de VRAIES politiques
        # de rétention au démarrage (AppConfig.ready). Ces tests supposent un
        # registre vide : on l'isole (snapshot + clear) pour rester hermétique
        # quel que soit l'ordre d'exécution ou ce que les apps ont enregistré,
        # puis on restaure l'état réel en teardown.
        self._saved = dict(retention._REGISTRY)
        retention.clear_registry()

    def tearDown(self):
        retention.clear_registry()
        retention._REGISTRY.update(self._saved)

    def test_register_and_list_policy(self):
        retention.register_retention_policy('demo', lambda now, apply_: 0)
        self.assertIn('demo', retention.list_retention_policies())

    def test_unregister_policy(self):
        retention.register_retention_policy('demo', lambda now, apply_: 0)
        retention.unregister_retention_policy('demo')
        self.assertNotIn('demo', retention.list_retention_policies())

    def test_run_all_policies_executes_registered_policy(self):
        calls = []

        def fake_sweep(now, apply_):
            calls.append((now, apply_))
            return 7

        retention.register_retention_policy('demo', fake_sweep)
        results = retention.run_all_policies(apply_=False)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], False)
        self.assertEqual(results, [
            {'name': 'demo', 'count': 7, 'statut': 'ok', 'erreur': ''}])

    def test_dry_run_transmits_apply_false_to_policy(self):
        """Le registre ne supprime rien LUI-MÊME — il transmet apply_=False,
        c'est à la politique de respecter le contrat dry-run."""
        received = {}

        def fake_sweep(now, apply_):
            received['apply_'] = apply_
            return 0

        retention.register_retention_policy('demo', fake_sweep)
        retention.run_all_policies(apply_=False)
        self.assertFalse(received['apply_'])

    def test_apply_true_is_transmitted_and_executes(self):
        received = {}

        def fake_sweep(now, apply_):
            received['apply_'] = apply_
            return 3

        retention.register_retention_policy('demo', fake_sweep)
        results = retention.run_all_policies(apply_=True)
        self.assertTrue(received['apply_'])
        self.assertEqual(results[0]['count'], 3)

    def test_each_execution_is_logged_as_retention_run(self):
        retention.register_retention_policy('demo', lambda now, apply_: 5)
        retention.run_all_policies(apply_=False)

        run = RetentionRun.objects.get(policy_name='demo')
        self.assertTrue(run.dry_run)
        self.assertEqual(run.count, 5)
        self.assertEqual(run.statut, RetentionRun.STATUT_OK)

    def test_apply_true_logs_dry_run_false(self):
        retention.register_retention_policy('demo', lambda now, apply_: 1)
        retention.run_all_policies(apply_=True)

        run = RetentionRun.objects.get(policy_name='demo')
        self.assertFalse(run.dry_run)

    def test_failing_policy_does_not_block_others(self):
        def failing(now, apply_):
            raise RuntimeError('boom')

        retention.register_retention_policy('bad', failing)
        retention.register_retention_policy('good', lambda now, apply_: 2)

        results = retention.run_all_policies(apply_=False)
        by_name = {r['name']: r for r in results}

        self.assertEqual(by_name['bad']['statut'], RetentionRun.STATUT_ECHEC)
        self.assertIn('boom', by_name['bad']['erreur'])
        self.assertEqual(by_name['good']['statut'], RetentionRun.STATUT_OK)
        self.assertEqual(by_name['good']['count'], 2)

        bad_run = RetentionRun.objects.get(policy_name='bad')
        self.assertEqual(bad_run.statut, RetentionRun.STATUT_ECHEC)
        self.assertIn('boom', bad_run.erreur)

    def test_no_policies_registered_returns_empty_list(self):
        self.assertEqual(retention.run_all_policies(apply_=False), [])


class RunRetentionCommandTests(TestCase):
    def setUp(self):
        # Voir RetentionRegistryTests.setUp — isolation du registre partagé.
        self._saved = dict(retention._REGISTRY)
        retention.clear_registry()

    def tearDown(self):
        retention.clear_registry()
        retention._REGISTRY.update(self._saved)

    def test_command_dry_run_by_default(self):
        received = {}

        def fake_sweep(now, apply_):
            received['apply_'] = apply_
            return 0

        retention.register_retention_policy('demo', fake_sweep)
        out = StringIO()
        call_command('run_retention', stdout=out)
        self.assertFalse(received['apply_'])
        self.assertIn('demo', out.getvalue())

    def test_command_apply_flag_applies(self):
        received = {}

        def fake_sweep(now, apply_):
            received['apply_'] = apply_
            return 4

        retention.register_retention_policy('demo', fake_sweep)
        out = StringIO()
        call_command('run_retention', '--apply', stdout=out)
        self.assertTrue(received['apply_'])

    def test_command_respects_settings_auto_apply(self):
        received = {}

        def fake_sweep(now, apply_):
            received['apply_'] = apply_
            return 0

        retention.register_retention_policy('demo', fake_sweep)
        with mock.patch('django.conf.settings.RETENTION_AUTO_APPLY', True):
            call_command('run_retention', stdout=StringIO())
        self.assertTrue(received['apply_'])

    def test_command_with_no_policies_warns(self):
        out = StringIO()
        call_command('run_retention', stdout=out)
        self.assertIn('aucune politique', out.getvalue())
