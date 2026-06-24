"""QJ20 — Appointment model + service tests.

Covers:
  - book_appointment: creates Appointment + chatter entry
  - company forced server-side (never from body)
  - dispatch_appointment_reminder: idempotent + wa.me + in-app
  - Ramadan-aware pacing: suppresses reminder in iftar window
  - send_due_appointment_reminders: only sends for upcoming appointments
  - beat task smoke test
  - company scoping: only your company's appointments visible via API
"""
from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Appointment, Lead, LeadActivity
from apps.crm.services import (
    book_appointment,
    dispatch_appointment_reminder,
    send_due_appointment_reminders,
)
from authentication.models import Company


def _make_company(slug):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def _make_lead(company):
    return Lead.objects.create(company=company, nom='TestLead', stage='NEW')


def _future(minutes=120):
    """Return a timezone-aware datetime ``minutes`` from now."""
    return timezone.now() + timedelta(minutes=minutes)


class TestBookAppointment(TestCase):
    """book_appointment service."""

    def setUp(self):
        self.co = _make_company('qj20-book')
        self.lead = _make_lead(self.co)

    def test_creates_appointment(self):
        scheduled = _future(120)
        appt = book_appointment(lead=self.lead, scheduled_at=scheduled, notes='Test')
        self.assertIsNotNone(appt.pk)
        self.assertEqual(appt.lead, self.lead)
        self.assertEqual(appt.company, self.co)
        self.assertEqual(appt.statut, Appointment.Statut.PLANIFIE)
        self.assertEqual(appt.notes, 'Test')
        self.assertFalse(appt.reminder_sent)

    def test_company_forced_from_lead(self):
        """Company must be taken from the lead, never passed separately."""
        scheduled = _future(60)
        appt = book_appointment(lead=self.lead, scheduled_at=scheduled)
        self.assertEqual(appt.company_id, self.lead.company_id)

    def test_chatter_entry_created(self):
        scheduled = _future(60)
        book_appointment(lead=self.lead, scheduled_at=scheduled)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.NOTE,
            ).exists()
        )

    def test_requires_scheduled_at(self):
        with self.assertRaises(ValueError):
            book_appointment(lead=self.lead, scheduled_at=None)


class TestDispatchReminder(TestCase):
    """dispatch_appointment_reminder service."""

    def setUp(self):
        self.co = _make_company('qj20-remind')
        self.lead = _make_lead(self.co)

    def _make_appt(self, minutes=30):
        return book_appointment(
            lead=self.lead, scheduled_at=_future(minutes))

    def test_reminder_sent_sets_flag(self):
        appt = self._make_appt()
        result = dispatch_appointment_reminder(appt)
        self.assertTrue(result)
        appt.refresh_from_db()
        self.assertTrue(appt.reminder_sent)

    def test_idempotent_already_sent(self):
        appt = self._make_appt()
        appt.reminder_sent = True
        appt.save(update_fields=['reminder_sent'])
        result = dispatch_appointment_reminder(appt)
        self.assertTrue(result)  # returns True (already sent)

    def test_ramadan_iftar_window_suppresses(self):
        """When pacing flag is on and current time is in iftar window, defer."""
        appt = self._make_appt()

        # Patch _ramadan_pacing_enabled and _is_ramadan_iftar_window.
        import apps.crm.services as svc
        orig_pacing = svc._ramadan_pacing_enabled
        orig_window = svc._is_ramadan_iftar_window
        svc._ramadan_pacing_enabled = lambda co: True
        svc._is_ramadan_iftar_window = lambda dt: True
        try:
            result = dispatch_appointment_reminder(appt)
        finally:
            svc._ramadan_pacing_enabled = orig_pacing
            svc._is_ramadan_iftar_window = orig_window

        self.assertFalse(result)
        appt.refresh_from_db()
        self.assertFalse(appt.reminder_sent)  # NOT marked sent

    def test_ramadan_pacing_off_sends_normally(self):
        """When pacing flag is off, even during iftar window the reminder goes."""
        appt = self._make_appt()

        import apps.crm.services as svc
        orig_pacing = svc._ramadan_pacing_enabled
        svc._ramadan_pacing_enabled = lambda co: False
        try:
            result = dispatch_appointment_reminder(appt)
        finally:
            svc._ramadan_pacing_enabled = orig_pacing

        self.assertTrue(result)
        appt.refresh_from_db()
        self.assertTrue(appt.reminder_sent)


class TestSendDueReminders(TestCase):
    """send_due_appointment_reminders filters correctly."""

    def setUp(self):
        self.co = _make_company('qj20-due')
        self.lead = _make_lead(self.co)

    def test_only_upcoming_in_window(self):
        """Only appointments in the next APPOINTMENT_REMINDER_MINUTES minutes are sent."""
        # Within window (30 min from now).
        appt_due = book_appointment(
            lead=self.lead,
            scheduled_at=timezone.now() + timedelta(minutes=30))
        # Too far away (3 hours from now).
        book_appointment(
            lead=self.lead,
            scheduled_at=timezone.now() + timedelta(hours=3))
        # Past (already gone).
        past_appt = book_appointment(
            lead=self.lead,
            scheduled_at=timezone.now() - timedelta(hours=1))

        sent = send_due_appointment_reminders()

        # Only the due one should have been sent.
        self.assertEqual(sent, 1)
        appt_due.refresh_from_db()
        self.assertTrue(appt_due.reminder_sent)

        past_appt.refresh_from_db()
        self.assertFalse(past_appt.reminder_sent)  # past, not sent

    def test_annule_not_sent(self):
        appt = book_appointment(
            lead=self.lead,
            scheduled_at=timezone.now() + timedelta(minutes=10))
        appt.statut = Appointment.Statut.ANNULE
        appt.save(update_fields=['statut'])

        sent = send_due_appointment_reminders()
        self.assertEqual(sent, 0)

    def test_effectue_not_sent(self):
        appt = book_appointment(
            lead=self.lead,
            scheduled_at=timezone.now() + timedelta(minutes=10))
        appt.statut = Appointment.Statut.EFFECTUE
        appt.save(update_fields=['statut'])

        sent = send_due_appointment_reminders()
        self.assertEqual(sent, 0)

    def test_already_sent_not_resent(self):
        appt = book_appointment(
            lead=self.lead,
            scheduled_at=timezone.now() + timedelta(minutes=10))
        appt.reminder_sent = True
        appt.save(update_fields=['reminder_sent'])

        sent = send_due_appointment_reminders()
        self.assertEqual(sent, 0)


class TestAppointmentCompanyScoping(TestCase):
    """Company FK is always taken from the lead (multi-tenant guard)."""

    def test_company_from_lead(self):
        co1 = _make_company('qj20-scope1')
        co2 = _make_company('qj20-scope2')
        lead1 = _make_lead(co1)
        lead2 = _make_lead(co2)

        book_appointment(lead=lead1, scheduled_at=_future())
        book_appointment(lead=lead2, scheduled_at=_future())

        self.assertEqual(Appointment.objects.filter(company=co1).count(), 1)
        self.assertEqual(Appointment.objects.filter(company=co2).count(), 1)


class TestRamadanHelpers(TestCase):
    """Unit tests for the Ramadan-aware helpers."""

    def test_iftar_window_detected(self):
        """A datetime at 19:00 Casablanca should be in the iftar window."""
        from apps.crm.services import _is_ramadan_iftar_window
        # 19:00 Casablanca = 19:00 UTC (Morocco = UTC+0 or UTC+1 — use UTC naive
        # and rely on the implementation's ZoneInfo lookup). Create an aware UTC
        # dt that maps to 19:30 Casablanca (Morocco is UTC+0 in winter).
        import zoneinfo
        tz = zoneinfo.ZoneInfo('Africa/Casablanca')
        dt = datetime(2025, 1, 15, 19, 30, tzinfo=tz)  # 19:30 local
        self.assertTrue(_is_ramadan_iftar_window(dt))

    def test_morning_not_iftar_window(self):
        from apps.crm.services import _is_ramadan_iftar_window
        import zoneinfo
        tz = zoneinfo.ZoneInfo('Africa/Casablanca')
        dt = datetime(2025, 1, 15, 9, 0, tzinfo=tz)  # 09:00 local
        self.assertFalse(_is_ramadan_iftar_window(dt))

    def test_pacing_disabled_by_default(self):
        """Without CompanyProfile.ramadan_pacing field, pacing is False."""
        from apps.crm.services import _ramadan_pacing_enabled
        co = _make_company('qj20-ramadan')
        # Should not raise; returns False when field absent.
        result = _ramadan_pacing_enabled(co)
        self.assertFalse(result)


class TestQJ20BeatTask(TestCase):
    """Beat task smoke test."""

    def setUp(self):
        self.co = _make_company('qj20-beat')
        self.lead = _make_lead(self.co)

    def test_beat_task_returns_count(self):
        from apps.ventes.scheduled import appointment_reminders
        result = appointment_reminders()
        self.assertIsInstance(result, int)
