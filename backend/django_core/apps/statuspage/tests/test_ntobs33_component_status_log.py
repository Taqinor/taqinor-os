"""NTOBS33 — historique brut des changements de statut d'un composant
(avant publication d'incident).

Le panneau frontend (``frontend/src/pages/parametres/HistoriqueStatutPage.
jsx``) est hors périmètre de cette lane (``frontend/src`` appartient à une
autre lane)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company
from core.health import STATUS_DEGRADED, STATUS_OK

from ..models import ComponentStatus, ComponentStatusLog
from ..tasks import rafraichir_composants

User = get_user_model()


class RafraichirComposantsLogsTransitionsTest(TestCase):
    def _fake_services(self, database='ok', cache='ok'):
        return [
            {'name': 'database', 'status': STATUS_OK if database == 'ok' else STATUS_DEGRADED},
            {'name': 'cache', 'status': STATUS_OK if cache == 'ok' else STATUS_DEGRADED},
            {'name': 'storage', 'status': STATUS_OK},
            {'name': 'broker', 'status': STATUS_OK},
            {'name': 'queue', 'status': STATUS_OK},
        ]

    def test_first_tick_logs_one_entry_per_component(self):
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                return_value=self._fake_services()):
            rafraichir_composants()
        # 4 composants publics + IA = 5 entrées (aucun statut antérieur).
        self.assertEqual(ComponentStatusLog.objects.count(), 5)
        self.assertTrue(
            ComponentStatusLog.objects.filter(ancien_statut='').exists())

    def test_unchanged_status_does_not_log_again(self):
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                return_value=self._fake_services()):
            rafraichir_composants()
            rafraichir_composants()
        # Toujours 5 (un par composant à la toute première détection),
        # aucune ligne supplémentaire au 2e tick identique.
        self.assertEqual(ComponentStatusLog.objects.count(), 5)

    def test_real_transition_creates_a_new_log_entry(self):
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                return_value=self._fake_services(database='ok')):
            rafraichir_composants()
        avant = ComponentStatusLog.objects.count()
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                return_value=self._fake_services(database='degraded')):
            rafraichir_composants()
        apres = ComponentStatusLog.objects.count()
        self.assertGreater(apres, avant)
        entry = ComponentStatusLog.objects.filter(composant='API').latest('id')
        self.assertEqual(entry.ancien_statut, ComponentStatus.Statut.OPERATIONAL)
        self.assertEqual(entry.nouveau_statut, ComponentStatus.Statut.DEGRADED)


class HistoriqueStatutEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-nt33')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial')
        self.directeur = User.objects.create_user(
            'directeur33', password='x', company=self.company,
            role=self.role_directeur)
        self.commercial = User.objects.create_user(
            'commercial33', password='x', company=self.company,
            role=self.role_commercial)
        self.log = ComponentStatusLog.objects.create(
            company=None, composant='API', region='EU-West/Hetzner',
            ancien_statut=ComponentStatus.Statut.OPERATIONAL,
            nouveau_statut=ComponentStatus.Statut.MAJOR_OUTAGE)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_directeur_lists_last_changes(self):
        resp = self._client(self.directeur).get(
            '/api/django/statuspage/historique-statut/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['composant'], 'API')

    def test_non_directeur_forbidden(self):
        resp = self._client(self.commercial).get(
            '/api/django/statuspage/historique-statut/')
        self.assertEqual(resp.status_code, 403)

    def test_prefill_incident_suggests_critical_severity_for_major_outage(self):
        resp = self._client(self.directeur).get(
            f'/api/django/statuspage/historique-statut/{self.log.pk}/'
            'prefill-incident/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['severite'], 'critique')
        self.assertEqual(resp.data['composants'], ['API'])
        # Le titre reste à écrire par le fondateur — jamais généré.
        self.assertEqual(resp.data['titre'], '')

    def test_prefill_never_creates_an_incident(self):
        from ..models import IncidentPublic
        avant = IncidentPublic.objects.count()
        self._client(self.directeur).get(
            f'/api/django/statuspage/historique-statut/{self.log.pk}/'
            'prefill-incident/')
        self.assertEqual(IncidentPublic.objects.count(), avant)
