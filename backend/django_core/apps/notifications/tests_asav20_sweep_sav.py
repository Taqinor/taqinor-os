"""ASAV20 — le balayage `_sweep_sav_breaching` suit le drapeau SLA
(`sav.selectors.ticket_en_retard_sla`), seulement si la société a le SLA
activé, avec UNE notification par ticket et par épisode de retard.

Run :
    python manage.py test apps.notifications.tests_asav20_sweep_sav -v2
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company, CustomUser
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket
from .models import Notification
from .sweeps import _sweep_sav_breaching
from .types_evenements import EventType


class SweepSavTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()

    def _societe(self, slug, *, sla):
        company, _ = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})
        CustomUser.objects.create_user(
            username=f'mgr_{slug}', password='x', company=company,
            role_legacy='admin')
        reglage = SavSlaSettings.get(company)
        reglage.sla_breach_enabled = sla
        reglage.save()
        return company, Client.objects.create(company=company, nom='Client')

    def _ticket(self, company, client, ref, **kw):
        return Ticket.objects.create(
            company=company, client=client, reference=ref,
            statut=Ticket.Statut.EN_COURS,
            date_ouverture=self.today - timedelta(days=8), **kw)

    def _notifs(self, company):
        return Notification.objects.filter(
            company=company, event_type=EventType.SAV_TICKET_BREACHING).count()

    def test_sans_sla_aucune(self):
        company, client = self._societe('asav20-off', sla=False)
        for i in range(3):
            self._ticket(company, client, f'T-A20-OFF-{i}')
        self.assertEqual(_sweep_sav_breaching(company), 0)
        self.assertEqual(self._notifs(company), 0)

    def test_retard_une_seule(self):
        company, client = self._societe('asav20-on', sla=True)
        self._ticket(company, client, 'T-A20-RETARD',
                     sla_due_at=self.today - timedelta(days=2))
        _sweep_sav_breaching(company)
        self.assertEqual(self._notifs(company), 1)
        _sweep_sav_breaching(company)
        self.assertEqual(self._notifs(company), 1)

    def test_pause_aucune(self):
        company, client = self._societe('asav20-pause', sla=True)
        self._ticket(company, client, 'T-A20-PAUSE',
                     sla_due_at=self.today - timedelta(days=1),
                     en_attente_client=True,
                     attente_depuis=self.today - timedelta(days=4))
        _sweep_sav_breaching(company)
        self.assertEqual(self._notifs(company), 0)
