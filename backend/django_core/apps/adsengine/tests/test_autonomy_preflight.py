"""ADSENG38 — Tests du préflight d'autonomie + go-live.

Prouve la garantie STRUCTURELLE : tant qu'une porte manque, ``activate`` REFUSE
(avec raisons FR) et le drapeau d'autonomie n'est jamais posé ; toutes les portes
vertes ⇒ activable, mais OFF par défaut (activation = geste explicite).
"""
import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import preflight
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, FlightPlan, GuardrailConfig,
    MetaConnection, RulePolicy,
)

TODAY = datetime.date(2026, 7, 13)


class AutonomyPreflightTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Auto Co', slug='auto-co')

    def tearDown(self):
        cache.clear()

    # ── Helpers : rendre chaque porte verte ─────────────────────────────────
    def _live_connection(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'})

    def _guardrails(self):
        GuardrailConfig.objects.create(company=self.company)

    def _alerts(self):
        RulePolicy.objects.create(
            company=self.company, template_key='zero_results', enabled=True)

    def _backlog(self):
        for i in range(12):
            asset = CreativeAsset.objects.create(
                company=self.company,
                asset_type=CreativeAsset.AssetType.STATIC,
                hook_id=f'H{i % 4}', policy_stamp={'passed': True})
            CreativeBacklogItem.objects.create(
                company=self.company, asset=asset,
                status=CreativeBacklogItem.Statut.EN_FILE)

    def _active_plan(self):
        FlightPlan.objects.create(
            company=self.company, name='Plan', start_date=TODAY,
            status=FlightPlan.Statut.ACTIF)

    def _all_green(self):
        """Rend TOUTES les portes vertes (dont sim acquittée + tests terrain)."""
        self._live_connection()
        self._guardrails()
        self._alerts()
        self._backlog()
        self._active_plan()
        preflight.acknowledge_simulation(self.company)

    # ── Refus tant qu'une porte manque ──────────────────────────────────────
    def test_empty_context_is_not_ready_and_lists_reasons(self):
        st = preflight.status(self.company, today=TODAY)
        self.assertFalse(st['ready'])
        self.assertFalse(st['active'])
        joined = ' '.join(st['missing_fr'])
        self.assertIn('connexion Meta', joined)
        self.assertIn('GuardrailConfig', joined)
        self.assertIn('Backlog insuffisant', joined)

    def test_activate_refused_until_all_green(self):
        # Presque tout vert SAUF les tests terrain (dry) → refus structurel.
        self._all_green()
        with self.assertRaises(preflight.AutonomyNotReady) as ctx:
            preflight.activate(self.company, today=TODAY)
        self.assertTrue(ctx.exception.missing_fr)
        # Le drapeau n'a PAS été posé.
        self.assertFalse(preflight.is_active(self.company))

    def test_each_gate_can_be_the_sole_blocker(self):
        # Tout vert (y compris tests terrain simulés), puis on casse UNE porte.
        with mock.patch.object(preflight.field_tests, 'pending_keys',
                               return_value=[]):
            self._all_green()
            # Retire les garde-fous → seule porte rouge.
            GuardrailConfig.objects.filter(company=self.company).delete()
            st = preflight.status(self.company, today=TODAY)
            self.assertFalse(st['ready'])
            self.assertEqual(
                [g['key'] for g in st['gates'] if not g['ok']],
                ['guardrails'])

    # ── Vert partout = activable, mais OFF par défaut ───────────────────────
    def test_all_green_is_ready_but_off_by_default(self):
        with mock.patch.object(preflight.field_tests, 'pending_keys',
                               return_value=[]):
            self._all_green()
            st = preflight.status(self.company, today=TODAY)
            self.assertTrue(st['ready'], st['missing_fr'])
            # OFF par défaut : ready ne veut PAS dire active.
            self.assertFalse(st['active'])
            self.assertFalse(preflight.is_active(self.company))

    def test_activate_when_all_green_sets_autonomy(self):
        with mock.patch.object(preflight.field_tests, 'pending_keys',
                               return_value=[]):
            self._all_green()
            st = preflight.activate(self.company, today=TODAY)
            self.assertTrue(st['active'])
            self.assertTrue(preflight.is_active(self.company))
            # Désactivation toujours possible (sécurité).
            preflight.deactivate(self.company)
            self.assertFalse(preflight.is_active(self.company))

    def test_field_tests_gate_reflects_pending_unknowns(self):
        # Par défaut (ADSENG37 dry) : la porte tests-terrain est ROUGE.
        gate = next(g for g in preflight.gates(self.company, today=TODAY)
                    if g.key == 'field_tests')
        self.assertFalse(gate.ok)
