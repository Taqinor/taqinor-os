"""ASAV15 — l'échéance SLA suit la priorité, l'ouverture et le client.

Un PATCH de ``priorite`` / ``date_ouverture`` / ``client`` (et l'édition en
masse de la priorité) recalcule ``sla_due_at`` et remet à zéro pré-alerte,
escalade et ``sla_breach`` (nouveau cycle). Un PATCH d'un autre champ ne
touche pas l'échéance.

Run :
    python manage.py test apps.sav.tests_asav15_sla_edition -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket

User = get_user_model()
BASE = '/api/django/sav/tickets'


class SlaEditionTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav15-co', defaults={'nom': 'ASAV15 Co'})
        self.admin = User.objects.create_user(
            username='asav15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.sla_par_priorite = {'urgente': {'resolution': 1}}
        sla.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV15')
        self.today = timezone.localdate()
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV15-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            priorite='normale', date_ouverture=self.today,
            created_by=self.admin)
        Ticket.objects.filter(pk=self.ticket.pk).update(
            sla_due_at=self.today + timedelta(days=7),
            sla_pre_alert_notifiee=True, sla_escalade_notifiee=True)
        self.ticket.refresh_from_db()

    def _patch(self, corps):
        r = self.api.patch(f'{BASE}/{self.ticket.pk}/', corps, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.ticket.refresh_from_db()

    def test_priorite_recalcule(self):
        self._patch({'priorite': 'urgente'})
        self.assertEqual(self.ticket.sla_due_at, self.today + timedelta(days=1))

    def test_date_ouverture_recalcule(self):
        ouverture = self.today - timedelta(days=30)
        self._patch({'date_ouverture': ouverture.isoformat()})
        self.assertEqual(self.ticket.sla_due_at, ouverture + timedelta(days=7))
        self.assertTrue(self.ticket.sla_breach)

    def test_lot_recalcule(self):
        self._patch({'priorite': 'urgente'})
        r = self.api.post(f'{BASE}/actions-groupees/', {
            'ids': [self.ticket.pk], 'operation': 'priorite',
            'priorite': 'normale'}, format='json')
        self.assertIn(r.status_code, (200, 207), r.content)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.sla_due_at, self.today + timedelta(days=7))

    def test_drapeaux_remis(self):
        self._patch({'priorite': 'urgente'})
        self.assertFalse(self.ticket.sla_pre_alert_notifiee)
        self.assertFalse(self.ticket.sla_escalade_notifiee)

    def test_autre_champ_inchange(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(
            sla_due_at=self.today + timedelta(days=5))
        self._patch({'description': 'Précision du client.'})
        self.assertEqual(self.ticket.sla_due_at, self.today + timedelta(days=5))
        self.assertTrue(self.ticket.sla_pre_alert_notifiee)
