"""ENG11 — Tests du brief hebdomadaire déterministe (v1, sans LLM).

Prouve : chiffres réels agrégés sur la fenêtre, niveau de fatigue vs seuil
2.0–2.5, 0-3 propositions liées (chacune avec reason_fr), rendu markdown, upsert
idempotent, et joignabilité + routage du beat hebdo.
"""
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import brief as brief_mod
from apps.adsengine.models import (
    AdCampaignMirror, EngineAction, InsightSnapshot, WeeklyBrief,
)
from apps.adsengine.tasks import generate_weekly_brief

NOW = datetime.date(2026, 7, 16)


class BriefGeneratorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Brief Co', slug='brief-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _snap(self, *, spend, results, freq, day=NOW):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=day, spend=spend, results=results, frequency=freq)

    def test_brief_aggregates_window_numbers(self):
        self._snap(spend='120.00', results=6, freq='1.80')
        brief = brief_mod.build_brief(self.company, now=NOW)
        data = brief.data
        self.assertEqual(data['spend_semaine'], '120.00')
        self.assertEqual(data['resultats_semaine'], 6)
        self.assertEqual(data['cpl_semaine'], '20.00')
        self.assertEqual(data['fatigue']['niveau'], 'ok')
        self.assertTrue(data['sla_ok'])
        self.assertIn('# Brief hebdomadaire', brief.markdown)

    def test_high_frequency_flags_fatigue_and_proposes_rotation(self):
        self._snap(spend='120.00', results=6, freq='2.80')
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertEqual(brief.data['fatigue']['niveau'], 'forte')
        # Une proposition de rotation créative est créée et liée.
        props = brief.data['propositions']
        self.assertTrue(any(
            p['kind'] == EngineAction.Kind.ROTATE_CREATIVE for p in props))
        self.assertTrue(all(p['reason_fr'] for p in props))

    def test_spend_without_results_proposes_pause(self):
        self._snap(spend='80.00', results=0, freq='1.10')
        brief = brief_mod.build_brief(self.company, now=NOW)
        kinds = {p['kind'] for p in brief.data['propositions']}
        self.assertIn(EngineAction.Kind.PAUSE, kinds)

    def test_proposals_capped_at_three(self):
        # 4 campagnes en fatigue forte → au plus 3 propositions.
        for i in range(4):
            camp = AdCampaignMirror.objects.create(
                company=self.company, meta_id=f'x{i}', name=f'C{i}',
                status='PAUSED')
            InsightSnapshot.objects.create(
                company=self.company,
                content_type=self.ct, object_id=camp.pk,
                date=NOW, spend='50.00', results=1, frequency='3.00')
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertLessEqual(len(brief.data['propositions']), 3)

    def test_idempotent_upsert_same_week(self):
        self._snap(spend='10.00', results=1, freq='1.00')
        b1 = brief_mod.build_brief(self.company, now=NOW)
        b2 = brief_mod.build_brief(self.company, now=NOW)
        self.assertEqual(b1.id, b2.id)
        self.assertEqual(WeeklyBrief.objects.filter(
            company=self.company).count(), 1)

    def test_out_of_window_snapshot_excluded(self):
        self._snap(spend='999.00', results=0, freq='1.0',
                   day=NOW - datetime.timedelta(days=30))
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertEqual(brief.data['spend_semaine'], '0')


class BriefTaskTests(TestCase):
    def test_task_noop_without_campaigns(self):
        Company.objects.create(nom='Empty', slug='empty')
        result = generate_weekly_brief()
        self.assertEqual(result, {'briefs_generated': 0})

    def test_task_generates_for_company_with_campaign(self):
        company = Company.objects.create(nom='Has', slug='has')
        AdCampaignMirror.objects.create(
            company=company, meta_id='c1', name='C', status='PAUSED')
        result = generate_weekly_brief()
        self.assertEqual(result, {'briefs_generated': 1})
        self.assertTrue(WeeklyBrief.objects.filter(company=company).exists())


class BriefBeatReachabilityTests(SimpleTestCase):
    def test_task_is_scheduled(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.generate_weekly_brief', names)

    def test_task_routed_to_scheduled(self):
        route = settings.CELERY_TASK_ROUTES['adsengine.generate_weekly_brief']
        self.assertEqual(route['queue'], 'scheduled')
