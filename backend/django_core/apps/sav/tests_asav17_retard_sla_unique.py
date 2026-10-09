"""ASAV17 — UNE définition du retard SLA (``sav.selectors``) pour le scan,
``performance_agent`` et ``file_action`` : l'échéance EFFECTIVE (pauses
« en attente client » décomptées), société sans SLA = jamais en retard.

Run :
    python manage.py test apps.sav.tests_asav17_retard_sla_unique -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.sav import selectors
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.views import scan_sla_breaches

User = get_user_model()


class RetardSlaUniqueTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()
        self.company, _ = Company.objects.get_or_create(
            slug='asav17-co', defaults={'nom': 'ASAV17 Co'})
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.save()
        self.tech = User.objects.create_user(
            username='asav17_tech', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV17')
        self._n = 0

    def _ticket(self, company=None, **champs):
        self._n += 1
        company = company or self.company
        valeurs = dict(
            company=company, reference=f'SAV-ASAV17-{self._n}',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            technicien_responsable=self.tech, created_by=self.tech)
        t = Ticket.objects.create(**valeurs)
        Ticket.objects.filter(pk=t.pk).update(**champs)
        t.refresh_from_db()
        return t

    def _en_pause(self, **extra):
        # Échéance brute J-1, en pause depuis J-3 → échéance effective J+2.
        return self._ticket(
            statut=Ticket.Statut.EN_COURS,
            date_ouverture=self.today - timedelta(days=8),
            sla_due_at=self.today - timedelta(days=1),
            en_attente_client=True,
            attente_depuis=self.today - timedelta(days=3), **extra)

    def _notifs(self, ticket):
        return Notification.objects.filter(
            company=self.company, event_type=EventType.SAV_TICKET_BREACHING,
            link=f'/sav/tickets/{ticket.pk}').count()

    def test_scan_pause_pas_en_retard(self):
        t = self._en_pause()
        self.assertFalse(selectors.ticket_en_retard_sla(t, self.today))
        scan_sla_breaches()
        t.refresh_from_db()
        self.assertFalse(t.sla_breach)
        self.assertEqual(self._notifs(t), 0)

    def test_scan_remet_false(self):
        t = self._en_pause(sla_breach=True)
        scan_sla_breaches()
        t.refresh_from_db()
        self.assertFalse(t.sla_breach)

    def test_scan_vrai_retard_marque_une_fois(self):
        t = self._ticket(
            statut=Ticket.Statut.EN_COURS,
            sla_due_at=self.today - timedelta(days=2))
        scan_sla_breaches()
        scan_sla_breaches()
        t.refresh_from_db()
        self.assertTrue(t.sla_breach)
        self.assertEqual(self._notifs(t), 1)

    def test_societe_sans_sla_jamais_en_retard(self):
        autre, _ = Company.objects.get_or_create(
            slug='asav17-off', defaults={'nom': 'ASAV17 Off'})
        t = self._ticket(
            company=autre, statut=Ticket.Statut.EN_COURS,
            sla_due_at=self.today - timedelta(days=5), sla_breach=True)
        # ASAV57 — le retard est calculé même interrupteur OFF, mais aucune
        # notification n'est émise.
        self.assertTrue(selectors.ticket_en_retard_sla(t, self.today))
        scan_sla_breaches()
        t.refresh_from_db()
        self.assertTrue(t.sla_breach)
        self.assertEqual(self._notifs(t), 0)

    def test_performance_agent_effectif(self):
        t = self._ticket(
            statut=Ticket.Statut.RESOLU, date_resolution=self.today,
            sla_due_at=self.today - timedelta(days=3), jours_pause=5)
        self.assertTrue(selectors.sla_respecte(t))
        agents = selectors.performance_agent(self.company)
        agents = agents['agents'] if isinstance(agents, dict) else agents
        ligne = next(a for a in agents if a['agent_id'] == self.tech.id)
        self.assertEqual(ligne['taux_respect_sla'], 100.0)

    def test_file_action_effectif(self):
        t = self._ticket(
            statut=Ticket.Statut.EN_COURS,
            date_ouverture=self.today - timedelta(days=12),
            sla_due_at=self.today + timedelta(days=2),
            date_premiere_reponse=timezone.now(),
            en_attente_client=True,
            attente_depuis=self.today - timedelta(days=10))
        res = selectors.file_action(self.company, today=self.today)
        self.assertNotIn(t.id, res['buckets']['a_relancer']['ids'])
