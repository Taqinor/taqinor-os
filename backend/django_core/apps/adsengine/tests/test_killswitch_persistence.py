"""PUB21 — Kill-switch + autonomie PERSISTÉS en base (survivent à un flush cache).

Régression : ces deux états ne vivaient qu'en cache Redis (TTL 30 j) — un flush
ou un redémarrage infra annulait SILENCIEUSEMENT un arrêt d'urgence. La DB
(``GuardrailConfig``) est désormais la SOURCE DE VÉRITÉ ; le cache n'est qu'un
accélérateur ré-échauffé sur miss. Comportement identique par ailleurs.
"""
import datetime

from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import flightrunner
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.models import FlightPlan, GuardrailConfig

TODAY = datetime.date(2026, 7, 1)


class KillSwitchPersistenceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Kill Co', slug='kill-co')
        self.plan = FlightPlan.objects.create(
            company=self.company, name='Plan', start_date=TODAY)
        self.runner = FlightRunner(
            self.plan, client=None, clock=lambda: TODAY)

    def tearDown(self):
        cache.clear()

    def test_off_by_default(self):
        self.assertFalse(self.runner.is_killed())
        self.assertFalse(
            GuardrailConfig.objects.filter(
                company=self.company, kill_switch_engaged=True).exists())

    def test_engage_writes_db_source_of_truth(self):
        self.runner.engage_kill_switch(reason_fr='Test sécurité')
        config = GuardrailConfig.objects.get(company=self.company)
        self.assertTrue(config.kill_switch_engaged)
        self.assertIsNotNone(config.kill_switch_engaged_at)
        self.assertEqual(config.kill_switch_reason, 'Test sécurité')

    def test_kill_switch_survives_cache_flush(self):
        # 1) engagé → 2) flush infra (cache vidé) → 3) TOUJOURS engagé (DB).
        self.runner.engage_kill_switch()
        self.assertTrue(self.runner.is_killed())

        cache.clear()  # simulate un flush/restart Redis

        # Un runner tout neuf (pas d'état en mémoire) le voit TOUJOURS engagé.
        fresh = FlightRunner(self.plan, client=None, clock=lambda: TODAY)
        self.assertTrue(fresh.is_killed())
        self.assertEqual(fresh.state(), FlightRunner.STATE_KILLED)

    def test_is_killed_rewarms_cache_from_db(self):
        self.runner.engage_kill_switch()
        cache.clear()
        # Après un miss, la lecture ré-échauffe le cache (accélérateur).
        self.assertTrue(self.runner.is_killed())
        self.assertTrue(bool(cache.get(self.runner._kill_key())))

    def test_release_clears_db_and_cache(self):
        self.runner.engage_kill_switch()
        self.runner.release_kill_switch()
        self.assertFalse(self.runner.is_killed())
        config = GuardrailConfig.objects.get(company=self.company)
        self.assertFalse(config.kill_switch_engaged)
        self.assertIsNone(config.kill_switch_engaged_at)
        # Un flush après relâche : toujours pas engagé (DB propre).
        cache.clear()
        self.assertFalse(self.runner.is_killed())


class AutonomyPersistenceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Auto Co', slug='auto-co')

    def tearDown(self):
        cache.clear()

    def test_off_by_default(self):
        self.assertFalse(flightrunner.is_autonomy_active(self.company))

    def test_set_active_writes_db(self):
        flightrunner.set_autonomy_active(self.company, True)
        config = GuardrailConfig.objects.get(company=self.company)
        self.assertTrue(config.autonomy_active)

    def test_autonomy_survives_cache_flush(self):
        flightrunner.set_autonomy_active(self.company, True)
        self.assertTrue(flightrunner.is_autonomy_active(self.company))
        cache.clear()  # flush infra
        # Toujours actif : la DB est la source de vérité.
        self.assertTrue(flightrunner.is_autonomy_active(self.company))

    def test_deactivate_clears_db_and_cache(self):
        flightrunner.set_autonomy_active(self.company, True)
        flightrunner.set_autonomy_active(self.company, False)
        config = GuardrailConfig.objects.get(company=self.company)
        self.assertFalse(config.autonomy_active)
        cache.clear()
        self.assertFalse(flightrunner.is_autonomy_active(self.company))
