"""VX210 — le snooze devient un rappel ACTIF, généralisé, déclenché par
l'événement métier. VX85 posait `snoozed_until` + exclusion passive : rien ne
RÉVEILLAIT l'item ni ne re-notifiait à l'échéance. Ce test couvre les DEUX
chemins de sortie :
  1) horloge — `snoozed_until` échu → réveil + notification.
  2) événement — `snooze_trigger_event='client_reply:<lead>'` survient AVANT
     l'échéance (une nouvelle `LeadActivity`) → réveil immédiat.
Et le snooze GÉNÉRIQUE (VX210(b)) d'une approbation hétérogène depuis « Ma
file » : masque puis ramène.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import Activity, ActivityType

User = get_user_model()


def _make_company(name='VX210 Co'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class Vx210ClockReveilTests(TestCase):
    """Chemin 1 — l'horloge : `snoozed_until` échu réveille + notifie."""

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company, 'vx210_clock')
        self.atype = ActivityType.objects.create(
            company=self.company, nom='Appel', icone='📞')

    def test_snoozed_activity_wakes_on_due_date_and_notifies(self):
        from .services import reveiller_snoozes

        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        act = Activity.objects.create(
            company=self.company, activity_type=self.atype,
            summary='Relancer le client', assigned_to=self.user,
            snoozed_until=yesterday, snoozed_at=timezone.now())

        woken = reveiller_snoozes(self.company)
        self.assertEqual(woken, 1)

        act.refresh_from_db()
        self.assertIsNone(act.snoozed_until)
        self.assertIsNone(act.snoozed_at)
        self.assertEqual(act.snooze_trigger_event, '')

        from apps.notifications.models import EventType, Notification
        notif = Notification.objects.filter(
            recipient=self.user, event_type=EventType.SNOOZE_REVEIL).first()
        self.assertIsNotNone(notif)
        self.assertIn('De retour', notif.title)

    def test_still_snoozed_activity_is_untouched(self):
        from .services import reveiller_snoozes

        tomorrow = timezone.now().date() + datetime.timedelta(days=3)
        act = Activity.objects.create(
            company=self.company, activity_type=self.atype,
            summary='Pas encore', assigned_to=self.user,
            snoozed_until=tomorrow, snoozed_at=timezone.now())

        woken = reveiller_snoozes(self.company)
        self.assertEqual(woken, 0)
        act.refresh_from_db()
        self.assertEqual(act.snoozed_until, tomorrow)

    def test_idempotent_second_pass_wakes_nothing(self):
        from .services import reveiller_snoozes

        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        Activity.objects.create(
            company=self.company, activity_type=self.atype,
            summary='X', assigned_to=self.user,
            snoozed_until=yesterday, snoozed_at=timezone.now())

        first = reveiller_snoozes(self.company)
        second = reveiller_snoozes(self.company)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)


class Vx210EventTriggerReveilTests(TestCase):
    """Chemin 2 — l'événement métier : `client_reply:<lead>` réveille avant
    même l'échéance, dès qu'une nouvelle `LeadActivity` arrive sur ce lead."""

    def setUp(self):
        self.company = _make_company('VX210 Event Co')
        self.user = _make_user(self.company, 'vx210_event')
        self.atype = ActivityType.objects.create(
            company=self.company, nom='Suivi', icone='📋')

    def _lead(self):
        from apps.crm.models import Lead
        return Lead.objects.create(
            company=self.company, nom='Lead VX210', telephone='+212600000099')

    def test_client_reply_wakes_before_due_date(self):
        from apps.crm.models import Lead, LeadActivity
        from apps.records.services import reveiller_snoozes, snooze_activity
        from django.contrib.contenttypes.models import ContentType

        lead = self._lead()
        far_future = timezone.now().date() + datetime.timedelta(days=30)
        ct = ContentType.objects.get_for_model(Lead)
        act = Activity.objects.create(
            company=self.company, activity_type=self.atype,
            summary='Attendre la réponse du client', assigned_to=self.user,
            content_type=ct, object_id=lead.id)
        snooze_activity(act, far_future, f'client_reply:{lead.id}')
        act.refresh_from_db()
        self.assertIsNotNone(act.snoozed_at)

        # Rien ne s'est passé — le sweep ne réveille pas encore (échéance
        # lointaine, aucune LeadActivity depuis la pose du snooze).
        self.assertEqual(reveiller_snoozes(self.company), 0)

        # Le client répond : une LeadActivity entrante arrive sur CE lead.
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.NOTE,
            body='Le client a répondu par email')

        woken = reveiller_snoozes(self.company)
        self.assertEqual(woken, 1)
        act.refresh_from_db()
        self.assertIsNone(act.snoozed_until)
        self.assertEqual(act.snooze_trigger_event, '')

    def test_prior_activity_before_snooze_does_not_wake_it(self):
        """Une LeadActivity ANTÉRIEURE à la pose du snooze ne le réveille
        jamais — seul un événement APRÈS `snoozed_at` compte."""
        from apps.crm.models import Lead, LeadActivity
        from apps.records.services import reveiller_snoozes, snooze_activity
        from django.contrib.contenttypes.models import ContentType

        lead = self._lead()
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.NOTE,
            body='Ancienne note, avant le snooze')

        far_future = timezone.now().date() + datetime.timedelta(days=30)
        ct = ContentType.objects.get_for_model(Lead)
        act = Activity.objects.create(
            company=self.company, activity_type=self.atype,
            summary='Attendre', assigned_to=self.user,
            content_type=ct, object_id=lead.id)
        snooze_activity(act, far_future, f'client_reply:{lead.id}')

        self.assertEqual(reveiller_snoozes(self.company), 0)
        act.refresh_from_db()
        self.assertIsNotNone(act.snoozed_until)


class Vx210SnoozeValidationTests(TestCase):

    def test_valid_snooze_trigger_event(self):
        from .services import valid_snooze_trigger_event
        self.assertTrue(valid_snooze_trigger_event(''))
        self.assertTrue(valid_snooze_trigger_event('client_reply:42'))
        self.assertTrue(valid_snooze_trigger_event('devis_signed:7'))
        self.assertTrue(valid_snooze_trigger_event('stock_arrive:3'))
        self.assertFalse(valid_snooze_trigger_event('invented:1'))
        self.assertFalse(valid_snooze_trigger_event('client_reply:'))
        self.assertFalse(valid_snooze_trigger_event('client_reply'))


class Vx210ApprobationSnoozeTests(TestCase):
    """VX210(b) — snoozer une approbation hétérogène la masque de « Ma
    file », puis la ramène au réveil."""

    def setUp(self):
        self.company = _make_company('VX210 Appro Co')
        self.approver = _make_user(
            self.company, 'vx210_appro', role_legacy='admin')
        self.requester = _make_user(self.company, 'vx210_req')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.approver)}')

    def _pending_automation_approval(self):
        from apps.automation.models import (
            ActionType, AutomationApproval, AutomationRule, TriggerType,
        )
        rule = AutomationRule.objects.create(
            company=self.company, nom='Règle VX210',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL, requires_approval=True)
        return AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action VX210',
            requested_by=self.requester)

    def test_snooze_masks_from_ma_file_then_reveils(self):
        approval = self._pending_automation_approval()

        # Avant snooze : visible dans Ma file.
        resp = self.api.get('/api/django/records/activities/ma-file/')
        self.assertEqual(resp.data['resume']['approbations'], 1)

        # Snooze pour demain.
        tomorrow = (timezone.now().date() + datetime.timedelta(days=1)).isoformat()
        resp = self.api.post(
            '/api/django/records/activities/snooze-approbation/',
            {'source': 'automation', 'id': approval.id, 'snoozed_until': tomorrow},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        # Masquée de Ma file.
        resp = self.api.get('/api/django/records/activities/ma-file/')
        self.assertEqual(resp.data['resume']['approbations'], 0)

        # Toujours visible dans l'inbox dédiée /approbations (jamais retirée
        # de la SOURCE — seule la file la masque).
        resp = self.api.get('/api/django/reporting/approbations-en-attente/')
        self.assertEqual(resp.data['total'], 1)

        # Le sweep la réveille (snoozed_until <= aujourd'hui simulé).
        from apps.notifications.models import SnoozedItem
        SnoozedItem.objects.filter(
            user=self.approver, source='automation', object_id=approval.id
        ).update(snoozed_until=timezone.now().date())
        from apps.notifications.sweeps import _sweep_reveiller_snoozes_approbations
        woken = _sweep_reveiller_snoozes_approbations(self.company)
        self.assertEqual(woken, 1)

        resp = self.api.get('/api/django/records/activities/ma-file/')
        self.assertEqual(resp.data['resume']['approbations'], 1)

    def test_unsnooze_makes_it_reappear_immediately(self):
        approval = self._pending_automation_approval()
        tomorrow = (timezone.now().date() + datetime.timedelta(days=1)).isoformat()
        self.api.post(
            '/api/django/records/activities/snooze-approbation/',
            {'source': 'automation', 'id': approval.id, 'snoozed_until': tomorrow},
            format='json')
        resp = self.api.get('/api/django/records/activities/ma-file/')
        self.assertEqual(resp.data['resume']['approbations'], 0)

        # Annule le snooze (snoozed_until absent).
        resp = self.api.post(
            '/api/django/records/activities/snooze-approbation/',
            {'source': 'automation', 'id': approval.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.api.get('/api/django/records/activities/ma-file/')
        self.assertEqual(resp.data['resume']['approbations'], 1)
