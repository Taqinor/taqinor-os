"""YEVNT5 — chaque notification émise (in-app / email / WhatsApp) laisse une
trace d'audit company-scopée (canal + destinataire + résultat).

Couverture :
  - notify() avec seulement in_app activé -> une ligne AuditLog action=notify.
  - notify() avec email activé -> une ligne AuditLog action=email en plus.
  - notify() avec whatsapp activé -> une ligne AuditLog action=whatsapp en plus.
  - l'échec de l'audit (recorder.record patché pour lever) n'empêche PAS
    l'envoi (la Notification in-app est quand même créée).
  - company-scoping : l'entrée d'audit porte la société du destinataire.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from authentication.models import Company

from .models import EventType, Notification, NotificationPreference

User = get_user_model()

# VX209(a) — `notify()` respecte désormais les heures calmes par défaut pour
# les événements non-critiques (`LEAD_ASSIGNED` en fait partie) : ces tests
# visent la piste d'audit des canaux, pas les heures calmes elles-mêmes — on
# fige l'horloge sur un mercredi en journée pour rester déterministe quelle
# que soit l'heure d'exécution de la CI.
_WEEKDAY_DAYTIME = timezone.make_aware(datetime.datetime(2026, 7, 8, 14, 0))


def _make_company(name='AuditNotifCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username, **kwargs):
    return User.objects.create_user(
        username=username, password='pw', company=company, **kwargs)


class NotifyAuditTrailTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company, 'audit_recipient')

    def test_in_app_notify_writes_audit_entry(self):
        from .services import notify
        notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')
        entries = AuditLog.objects.filter(action=AuditLog.Action.NOTIFY)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.company_id, self.company.pk)
        self.assertIn('lead_assigned', entry.detail)
        self.assertIn('in_app', entry.detail)

    def test_email_channel_writes_its_own_audit_entry(self):
        from .services import notify
        NotificationPreference.objects.create(
            user=self.user, company=self.company,
            event_type=EventType.LEAD_ASSIGNED, email=True)
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_WEEKDAY_DAYTIME), mock.patch(
                'apps.notifications.services._dispatch_email',
                return_value=True) as mocked:
            notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')
        self.assertTrue(mocked.called)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.EMAIL).count(), 1)

    def test_whatsapp_channel_writes_its_own_audit_entry(self):
        from .services import notify
        NotificationPreference.objects.create(
            user=self.user, company=self.company,
            event_type=EventType.LEAD_ASSIGNED, whatsapp=True)
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_WEEKDAY_DAYTIME), mock.patch(
                'apps.notifications.services._dispatch_whatsapp',
                return_value=True) as mocked:
            notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')
        self.assertTrue(mocked.called)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.WHATSAPP).count(), 1)

    def test_audit_records_failed_channel_result(self):
        from .services import notify
        NotificationPreference.objects.create(
            user=self.user, company=self.company,
            event_type=EventType.LEAD_ASSIGNED, email=True)
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_WEEKDAY_DAYTIME), mock.patch(
                'apps.notifications.services._dispatch_email',
                return_value=False):
            notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')
        entry = AuditLog.objects.filter(action=AuditLog.Action.EMAIL).first()
        self.assertIsNotNone(entry)
        self.assertIn('échoué', entry.detail)

    def test_audit_write_failure_never_blocks_notification(self):
        """L'échec de l'écriture d'audit n'empêche pas l'envoi de la
        notification in-app elle-même."""
        from .services import notify
        with mock.patch(
                'apps.audit.recorder.record',
                side_effect=RuntimeError('boom')):
            n = notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')
        self.assertIsNotNone(n)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)

    def test_no_audit_entry_when_in_app_preference_disabled(self):
        """Cohérent avec le comportement existant : préférence in_app=False →
        pas de Notification créée → pas d'audit `notify` pour ce canal
        (mais aucun crash)."""
        from .services import notify
        NotificationPreference.objects.create(
            user=self.user, company=self.company,
            event_type=EventType.LEAD_ASSIGNED, in_app=False)
        notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.NOTIFY).count(), 0)
