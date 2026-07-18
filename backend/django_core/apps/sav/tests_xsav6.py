"""XSAV6 — Pré-alerte SLA (J-x) + escalade à la violation.

Couvre :
  * OFF par défaut (sla_warning_days=0, escalade_activee=False) → aucun effet ;
  * pré-alerte au technicien assigné à J-x avant l'échéance ;
  * escalade au tier responsable/direction (managers) après la violation ;
  * idempotence : un ticket déjà notifié pour un niveau n'est pas re-notifié
    au re-passage du sweep ;
  * migration additive (défauts 0 / False).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav6 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.notifications.models import Notification
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.views import scan_sla_pre_alerts_and_escalations

User = get_user_model()


def make_company(slug='sav-xsav6', nom='Sav Co XSAV6'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XSAV6PreAlertEscalationTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.tech = User.objects.create_user(
            username='xsav6_tech', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav6-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV6', client=self.client_obj)

    def _ticket(self, sla_due_at, **kw):
        defaults = dict(
            company=self.company, reference=f'SAV-XSAV6-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
            technicien_responsable=self.tech, sla_due_at=sla_due_at,
            created_by=self.admin)
        defaults.update(kw)
        return Ticket.objects.create(**defaults)

    def test_off_par_defaut_aucun_effet(self):
        self._ticket(date.today() + timedelta(days=1))
        result = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(result['pre_alerts'], 0)
        self.assertEqual(result['escalations'], 0)

    def test_pre_alerte_j_moins_x_au_technicien(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_warning_days = 2
        sla.save(update_fields=['sla_warning_days'])
        ticket = self._ticket(date.today() + timedelta(days=1))

        result = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(result['pre_alerts'], 1)
        ticket.refresh_from_db()
        self.assertTrue(ticket.sla_pre_alert_notifiee)
        self.assertTrue(
            Notification.objects.filter(recipient=self.tech).exists())

    def test_pre_alerte_idempotente(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_warning_days = 2
        sla.save(update_fields=['sla_warning_days'])
        self._ticket(date.today() + timedelta(days=1))

        r1 = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(r1['pre_alerts'], 1)
        r2 = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(r2['pre_alerts'], 0)

    def test_escalade_au_tier_responsable_apres_violation(self):
        sla = SavSlaSettings.get(self.company)
        sla.escalade_activee = True
        sla.save(update_fields=['escalade_activee'])
        ticket = self._ticket(date.today() - timedelta(days=1))

        Notification.objects.all().delete()
        result = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(result['escalations'], 1)
        ticket.refresh_from_db()
        self.assertTrue(ticket.sla_escalade_notifiee)
        # Escalade au tier admin (managers), pas seulement au technicien.
        self.assertTrue(
            Notification.objects.filter(recipient=self.admin).exists())

    def test_escalade_idempotente(self):
        sla = SavSlaSettings.get(self.company)
        sla.escalade_activee = True
        sla.save(update_fields=['escalade_activee'])
        self._ticket(date.today() - timedelta(days=1))

        r1 = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(r1['escalations'], 1)
        r2 = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(r2['escalations'], 0)

    def test_migration_defauts(self):
        other = make_company(slug='sav-xsav6-other', nom='Sav Co XSAV6 Other')
        sla = SavSlaSettings.get(other)
        self.assertEqual(sla.sla_warning_days, 0)
        self.assertFalse(sla.escalade_activee)

    # ── WIR30 — beat quotidien (tâche Celery jamais planifiée jusqu'ici) ────

    def test_task_registered_in_beat_schedule_and_routes(self):
        from django.conf import settings
        from erp_agentique.celery import app
        task_names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn(
            'sav.scan_sla_pre_alerts_and_escalations_quotidien', task_names)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES[
                'sav.scan_sla_pre_alerts_and_escalations_quotidien']['queue'],
            'scheduled')

    def test_task_wrapper_delegates_to_scan(self):
        from apps.sav.tasks import (
            scan_sla_pre_alerts_and_escalations_quotidien,
        )
        sla = SavSlaSettings.get(self.company)
        sla.sla_warning_days = 2
        sla.save(update_fields=['sla_warning_days'])
        ticket = self._ticket(date.today() + timedelta(days=1))

        result = scan_sla_pre_alerts_and_escalations_quotidien()
        self.assertEqual(result['pre_alerts'], 1)
        ticket.refresh_from_db()
        self.assertTrue(ticket.sla_pre_alert_notifiee)
