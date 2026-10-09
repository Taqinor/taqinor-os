"""ASAV57 (D-ASAV-5 Q2 a) — l'interrupteur `sla_breach_enabled` ne gouverne
plus que les NOTIFICATIONS : l'échéance et le retard sont toujours calculés.

Run :
    python manage.py test apps.sav.tests_asav57_sla_interrupteur -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.services import compute_sla_due_at
from apps.sav.tasks import scan_sla_breaches

User = get_user_model()


class SlaInterrupteurTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav57-co', defaults={'nom': 'ASAV57 Co'})
        self.tech = User.objects.create_user(
            username='asav57_tech', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV57')
        self.today = timezone.localdate()
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = False
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.save()

    def _ticket(self, ref):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
            technicien_responsable=self.tech,
            date_ouverture=self.today - timedelta(days=10),
            sla_due_at=self.today - timedelta(days=3))

    def _notifs(self, ticket):
        return Notification.objects.filter(
            company=self.company, event_type=EventType.SAV_TICKET_BREACHING,
            link=f'/sav/tickets/{ticket.pk}').count()

    def test_echeance_sans_notification(self):
        due = compute_sla_due_at(
            self.company, self.client_obj, 'normale', self.today)
        self.assertEqual(due, self.today + timedelta(days=7))
        t = self._ticket('SAV-A57-1')
        scan_sla_breaches()
        t.refresh_from_db()
        self.assertTrue(t.sla_breach)
        self.assertEqual(self._notifs(t), 0)

    def test_notification_si_active(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.save()
        t = self._ticket('SAV-A57-2')
        scan_sla_breaches()
        t.refresh_from_db()
        self.assertTrue(t.sla_breach)
        self.assertEqual(self._notifs(t), 1)
