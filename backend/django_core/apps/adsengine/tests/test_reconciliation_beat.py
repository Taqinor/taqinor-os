"""PUB19 — Câblage de ``run_daily_reconciliation`` en beat quotidien.

Avant : la fonction persist+alerte de ``reconciliation.py`` était morte (aucun
beat — seul le CSV on-demand appelait ``reconcile``). Prouve que le beat est
planifié + routé, qu'il PERSISTE un snapshot quotidien, et qu'une divergence
au-delà du seuil émet une ``EngineAlert`` 🟠.
"""
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead

from apps.adsengine import tasks
from apps.adsengine.models import (
    AdCampaignMirror, EngineAlert, InsightSnapshot, ReconciliationSnapshot,
)

DAY = datetime.date.today()


class BeatRegistrationTests(SimpleTestCase):
    def test_beat_scheduled_and_routed(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.run_daily_reconciliation', names)
        route = settings.CELERY_TASK_ROUTES[
            'adsengine.run_daily_reconciliation']
        self.assertEqual(route['queue'], 'scheduled')


class ReconciliationBeatTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RB Co', slug='rb-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Solaire Casa',
            status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _meta(self, results):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=DAY, results=results, spend='300.00')

    def _form_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect',
            source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
            meta_campaign_id='c1')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.make_aware(
                datetime.datetime.combine(DAY, datetime.time(12, 0))))
        return lead

    def test_beat_persists_snapshot_and_alerts_on_divergence(self):
        self._meta(10)                 # Meta = 10 leads
        for _ in range(3):
            self._form_lead()          # ERP = 3 leads → écart 7 (divergent)
        result = tasks.run_daily_reconciliation()
        self.assertEqual(result['companies'], 1)

        snap = ReconciliationSnapshot.objects.get(
            company=self.company, campaign=self.camp, date=DAY)
        self.assertEqual(snap.meta_leads, 10)
        self.assertEqual(snap.erp_leads, 3)
        self.assertEqual(snap.status, ReconciliationSnapshot.Statut.ECART)
        # Divergence au-delà du seuil → EngineAlert 🟠.
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company,
            detail__kind='reconciliation_divergence').exists())

    def test_beat_no_alert_when_aligned(self):
        self._meta(3)
        for _ in range(3):
            self._form_lead()
        tasks.run_daily_reconciliation()
        snap = ReconciliationSnapshot.objects.get(
            company=self.company, campaign=self.camp, date=DAY)
        self.assertEqual(snap.status, ReconciliationSnapshot.Statut.OK)
        self.assertFalse(EngineAlert.objects.filter(
            company=self.company,
            detail__kind='reconciliation_divergence').exists())


class ReconciliationBeatNoopTests(TestCase):
    def test_noop_without_any_campaign(self):
        Company.objects.create(nom='Empty', slug='empty')
        result = tasks.run_daily_reconciliation()
        self.assertEqual(result, {'companies': 0, 'snapshots': 0})
        self.assertEqual(ReconciliationSnapshot.objects.count(), 0)
