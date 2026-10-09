"""ASAV16 — le cycle SLA suit les transitions : la résolution clôt la pause
« en attente client » (l'échéance ne glisse plus), la réouverture repart de
la date de réouverture (D-ASAV-5) et remet les drapeaux d'alerte à False.

Run :
    python manage.py test apps.sav.tests_asav16_cycle_sla -v2
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


class CycleSlaTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav16-co', defaults={'nom': 'ASAV16 Co'})
        self.admin = User.objects.create_user(
            username='asav16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV16')
        self.today = timezone.localdate()

    def _ticket(self, ref, **kw):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, priorite='normale',
            date_ouverture=self.today - timedelta(days=5),
            sla_due_at=self.today + timedelta(days=2),
            created_by=self.admin, **kw)

    def _post(self, ticket, action):
        r = self.api.post(f'{BASE}/{ticket.pk}/{action}/', {}, format='json')
        self.assertIn(r.status_code, (200, 201), (action, r.content))
        ticket.refresh_from_db()

    def test_resolution_clot_pause(self):
        t = self._ticket('SAV-A16-1', en_attente_client=True,
                         attente_depuis=self.today - timedelta(days=1))
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        self.assertFalse(t.en_attente_client)
        self.assertIsNone(t.attente_depuis)
        self.assertEqual(t.jours_pause, 1)

    def test_echeance_figee_apres_resolution(self):
        t = self._ticket('SAV-A16-2', en_attente_client=True,
                         attente_depuis=self.today - timedelta(days=1))
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        apres = t.sla_due_at_effectif(today=self.today)
        plus_tard = t.sla_due_at_effectif(today=self.today + timedelta(days=10))
        self.assertEqual(apres, plus_tard)

    def test_reouverture_nouvelle_echeance(self):
        t = self._ticket('SAV-A16-3')
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        self._post(t, 'reouvrir')
        self.assertEqual(t.sla_due_at, self.today + timedelta(days=7))
        self.assertFalse(t.en_attente_client)
        self.assertEqual(t.jours_pause, 0)

    def test_drapeaux_remis_reouverture(self):
        t = self._ticket('SAV-A16-4', sla_pre_alert_notifiee=True,
                         sla_escalade_notifiee=True)
        self._post(t, 'demarrer')
        self._post(t, 'resoudre')
        self._post(t, 'reouvrir')
        self.assertFalse(t.sla_pre_alert_notifiee)
        self.assertFalse(t.sla_escalade_notifiee)
