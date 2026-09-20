"""NTOBS26 — ``core.events.maintenance_window_announced`` est émis à la
CRÉATION d'une fenêtre de maintenance (``MaintenanceWindowListCreateView.
perform_create``) : annonce immédiate côté webhook sortant, distincte du
rappel in-app 24h/1h avant l'échéance (NTOBS9, ``core.notify_registry``,
resté inchangé — voir ``test_ntobs9_maintenance_window.py``)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company
from core import events
from core.maintenance_windows import MaintenanceWindow

User = get_user_model()


class MaintenanceWindowAnnouncedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs26-acme')
        self.role_admin_fiabilite = Role.objects.create(
            company=self.company, nom='Administration Fiabilité',
            permissions=['fiabilite_administration'])
        self.admin = User.objects.create_user(
            'admfiab26', password='x', company=self.company,
            role=self.role_admin_fiabilite)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

        self.recus = []
        events.maintenance_window_announced.connect(
            self._capter, dispatch_uid='test_ntobs26_annonce')
        self.addCleanup(
            events.maintenance_window_announced.disconnect,
            dispatch_uid='test_ntobs26_annonce')

    def _capter(self, sender, **kwargs):
        self.recus.append(kwargs)

    def _payload(self):
        now = timezone.now()
        return {
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Bascule infra planifiée.',
        }

    def test_creation_via_api_emet_le_signal(self):
        resp = self.api.post(
            '/api/django/core/maintenance-windows/', self._payload())
        self.assertEqual(resp.status_code, 201, resp.data)

        self.assertEqual(len(self.recus), 1)
        charge = self.recus[0]
        fenetre = MaintenanceWindow.objects.get(id=resp.data['id'])
        self.assertEqual(charge['fenetre'].pk, fenetre.pk)
        self.assertEqual(charge['company'], self.company)
        self.assertEqual(charge['user'], self.admin)

    def test_un_abonne_qui_leve_ne_bloque_pas_la_creation(self):
        def casse(sender, **kwargs):
            raise RuntimeError('webhook injoignable')

        events.maintenance_window_announced.connect(
            casse, dispatch_uid='test_ntobs26_casse')
        self.addCleanup(
            events.maintenance_window_announced.disconnect,
            dispatch_uid='test_ntobs26_casse')

        resp = self.api.post(
            '/api/django/core/maintenance-windows/', self._payload())
        self.assertEqual(resp.status_code, 201, resp.data)
