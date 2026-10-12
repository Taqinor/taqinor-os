"""NTOBS9 — fenêtres de maintenance planifiées, annoncées in-app par région
avant qu'elles n'arrivent."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role

from core.maintenance_windows import MaintenanceWindow, notifier_fenetres_a_venir

User = get_user_model()


class NotifierFenetresAVenirTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs9')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.directeur = User.objects.create_user(
            'directeur9', password='x', company=self.company,
            role=self.role_directeur)

    def test_notifies_once_at_24h_threshold(self):
        now = timezone.now()
        fenetre = MaintenanceWindow.objects.create(
            company=self.company, debute_le=now + timezone.timedelta(hours=23),
            termine_le=now + timezone.timedelta(hours=24),
            description='Bascule infra planifiée.')
        with mock.patch('core.notify_registry.notify') as notify_mock:
            n1 = notifier_fenetres_a_venir(now=now)
            n2 = notifier_fenetres_a_venir(now=now)
        fenetre.refresh_from_db()
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 0)
        self.assertTrue(fenetre.notifie_24h_avant)
        self.assertFalse(fenetre.notifie_1h_avant)
        self.assertEqual(notify_mock.call_count, 1)

    def test_notifies_both_thresholds_when_within_1h(self):
        now = timezone.now()
        fenetre = MaintenanceWindow.objects.create(
            company=self.company,
            debute_le=now + timezone.timedelta(minutes=30),
            termine_le=now + timezone.timedelta(hours=1),
            description='Fenêtre imminente.')
        with mock.patch('core.notify_registry.notify'):
            notifier_fenetres_a_venir(now=now)
        fenetre.refresh_from_db()
        self.assertTrue(fenetre.notifie_24h_avant)
        self.assertTrue(fenetre.notifie_1h_avant)

    def test_far_future_window_is_not_notified_yet(self):
        now = timezone.now()
        MaintenanceWindow.objects.create(
            company=self.company, debute_le=now + timezone.timedelta(days=5),
            termine_le=now + timezone.timedelta(days=5, hours=1),
            description='Trop loin.')
        with mock.patch('core.notify_registry.notify') as notify_mock:
            n = notifier_fenetres_a_venir(now=now)
        self.assertEqual(n, 0)
        self.assertFalse(notify_mock.called)

    def test_system_wide_window_notifies_admins_of_every_company(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs9')
        Role.objects.create(company=autre, nom='Directeur')
        User.objects.create_user(
            'directeur9b', password='x', company=autre,
            role=Role.objects.get(company=autre, nom='Directeur'))
        now = timezone.now()
        MaintenanceWindow.objects.create(
            company=None, debute_le=now + timezone.timedelta(minutes=30),
            termine_le=now + timezone.timedelta(hours=1),
            description='Maintenance système large.')
        with mock.patch('core.notify_registry.notify') as notify_mock:
            notifier_fenetres_a_venir(now=now)
        # Les deux directeurs (deux sociétés) sont notifiés — 2 appels par
        # seuil (24h + 1h) x 2 admins = 4.
        self.assertEqual(notify_mock.call_count, 4)


class FenetresActivesEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs9b')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_upcoming_window_within_72h_is_active(self):
        now = timezone.now()
        MaintenanceWindow.objects.create(
            company=self.company, debute_le=now + timezone.timedelta(hours=48),
            termine_le=now + timezone.timedelta(hours=49),
            description='Bientôt.')
        resp = self.client.get('/api/django/core/maintenance-windows/actives/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_window_beyond_72h_is_not_active(self):
        now = timezone.now()
        MaintenanceWindow.objects.create(
            company=self.company, debute_le=now + timezone.timedelta(days=10),
            termine_le=now + timezone.timedelta(days=10, hours=1),
            description='Loin.')
        resp = self.client.get('/api/django/core/maintenance-windows/actives/')
        self.assertEqual(len(resp.data), 0)

    def test_another_companys_window_never_shown(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs9c')
        now = timezone.now()
        MaintenanceWindow.objects.create(
            company=autre, debute_le=now + timezone.timedelta(hours=1),
            termine_le=now + timezone.timedelta(hours=2),
            description='Pas pour moi.')
        resp = self.client.get('/api/django/core/maintenance-windows/actives/')
        self.assertEqual(len(resp.data), 0)

    def test_cancelled_window_disappears(self):
        now = timezone.now()
        fenetre = MaintenanceWindow.objects.create(
            company=self.company, debute_le=now + timezone.timedelta(hours=1),
            termine_le=now + timezone.timedelta(hours=2),
            description='Annulée bientôt.',
            statut=MaintenanceWindow.Statut.ANNULE)
        resp = self.client.get('/api/django/core/maintenance-windows/actives/')
        self.assertEqual(len(resp.data), 0)
        self.assertEqual(fenetre.statut, MaintenanceWindow.Statut.ANNULE)


class MaintenanceWindowPermissionTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs9d')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial')
        self.directeur = User.objects.create_user(
            'directeur9c', password='x', company=self.company,
            role=self.role_directeur)
        self.commercial = User.objects.create_user(
            'commercial9', password='x', company=self.company,
            role=self.role_commercial)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_directeur_can_create_window(self):
        now = timezone.now()
        payload = {
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Test',
        }
        resp = self._client(self.directeur).post(
            '/api/django/core/maintenance-windows/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_non_directeur_cannot_create_window(self):
        resp = self._client(self.commercial).post(
            '/api/django/core/maintenance-windows/', {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_non_superuser_directeur_cannot_target_another_company(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs9d')
        now = timezone.now()
        payload = {
            'company': autre.id,
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Tentative cross-tenant.',
        }
        resp = self._client(self.directeur).post(
            '/api/django/core/maintenance-windows/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['company'], self.company.id)

    def test_non_superuser_directeur_cannot_target_system_wide(self):
        now = timezone.now()
        payload = {
            'company': None,
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Tentative système large.',
        }
        # ``format='json'`` OBLIGATOIRE ici : le format par defaut du client DRF
        # est multipart, et ``encode_multipart`` leve un TypeError sur une
        # valeur None (« Cannot encode None for key 'company' ») — le test
        # n'atteignait donc jamais la vue. L'assertion, elle, ne bouge pas :
        # une societe posee a None dans le corps doit rester ignoree au profit
        # de celle de l'utilisateur.
        resp = self._client(self.directeur).post(
            '/api/django/core/maintenance-windows/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['company'], self.company.id)

    def test_annuler_notifies_and_sets_statut(self):
        now = timezone.now()
        fenetre = MaintenanceWindow.objects.create(
            company=self.company, debute_le=now + timezone.timedelta(hours=1),
            termine_le=now + timezone.timedelta(hours=2), description='X')
        with mock.patch('core.notify_registry.notify') as notify_mock:
            resp = self._client(self.directeur).post(
                f'/api/django/core/maintenance-windows/{fenetre.pk}/annuler/')
        self.assertEqual(resp.status_code, 200)
        fenetre.refresh_from_db()
        self.assertEqual(fenetre.statut, MaintenanceWindow.Statut.ANNULE)
        self.assertTrue(notify_mock.called)


class AuditRegistryTest(SimpleTestCase):
    """ENF20 — ``core.audit_registry`` : même inversion de dépendance que
    ``core.notify_registry`` (``core`` n'importe jamais ``apps.audit``)."""

    def setUp(self):
        from core import audit_registry
        self.registry = audit_registry
        self._avant = (audit_registry._RECORD, audit_registry._CURRENT_USER)
        audit_registry.desenregistrer()

    def tearDown(self):
        self.registry._RECORD, self.registry._CURRENT_USER = self._avant

    def test_sans_enregistreur_no_op_et_log(self):
        with self.assertLogs('core.audit_registry', level='DEBUG') as logs:
            self.assertIsNone(self.registry.record('update', detail='x'))
        self.assertIn('aucun enregistreur', logs.output[0])
        self.assertIsNone(self.registry.current_user())

    def test_enregistre_relaie_les_kwargs_tels_quels(self):
        record_mock = mock.Mock(return_value=None)
        user = object()
        self.registry.enregistrer(record_mock, current_user=lambda: user)
        self.registry.record(
            'security_alert', user=None, company='co', detail='SOD : x')
        record_mock.assert_called_once_with(
            'security_alert', user=None, company='co', detail='SOD : x')
        self.assertIs(self.registry.current_user(), user)

    def test_kwarg_user_absent_reste_absent(self):
        # ``recorder.record`` distingue « user non fourni » (acteur courant)
        # de ``user=None`` (système) : le registre ne doit rien injecter.
        record_mock = mock.Mock()
        self.registry.enregistrer(record_mock)
        self.registry.record('create', instance='i', detail='d')
        self.assertNotIn('user', record_mock.call_args.kwargs)
