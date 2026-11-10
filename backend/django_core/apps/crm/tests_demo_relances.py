"""NTDMO29 — tâche quotidienne : relances des leads de société démo ré-ancrées."""
import datetime

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Lead
from apps.crm.tasks import reancrer_relances_demo


class ReancrerRelancesDemoTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        passe = self.today - datetime.timedelta(days=20)
        self.demo = Company.objects.create(
            nom='Démo 29', slug='demo-29', est_demo=True)
        self.reelle = Company.objects.create(nom='Réelle 29', slug='reelle-29')
        self.leads_demo = [
            Lead.objects.create(company=self.demo, nom=f'D{i}',
                                relance_date=passe) for i in range(4)]
        self.lead_reel = Lead.objects.create(
            company=self.reelle, nom='R', relance_date=passe)

    def test_demo_a_au_moins_trois_relances_futures(self):
        n = reancrer_relances_demo(today=self.today)
        self.assertEqual(n, 4)
        futures = Lead.objects.filter(
            company=self.demo, relance_date__gt=self.today).count()
        self.assertGreaterEqual(futures, 3)
        for lead in Lead.objects.filter(company=self.demo):
            self.assertLessEqual(
                lead.relance_date, self.today + datetime.timedelta(days=5))

    def test_societe_non_demo_jamais_touchee(self):
        avant = self.lead_reel.relance_date
        reancrer_relances_demo(today=self.today)
        self.lead_reel.refresh_from_db()
        self.assertEqual(self.lead_reel.relance_date, avant)

    def test_idempotent(self):
        reancrer_relances_demo(today=self.today)
        self.assertEqual(reancrer_relances_demo(today=self.today), 0)

    def test_beat_et_route_declares(self):
        from erp_agentique.celery import app
        taches = {v['task'] for v in app.conf.beat_schedule.values()}
        self.assertIn('crm.reancrer_relances_demo', taches)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['crm.reancrer_relances_demo']['queue'],
            'scheduled')
