"""NTOBS1 — page de statut publique : composants + incidents, jamais de fuite
société."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from ..models import ComponentStatus, IncidentPublic, IncidentUpdate
from ..tasks import rafraichir_composants


class PublicStatusEndpointTest(TestCase):
    def setUp(self):
        # Le cache mémoire du process N'EST PAS réinitialisé par le rollback
        # de transaction entre tests (contrairement à la DB) — un test
        # précédent qui a peuplé PUBLIC_STATUS_CACHE_KEY polluerait celui-ci.
        cache.clear()
        self.client = APIClient()
        self.company = Company.objects.create(nom='Acme', slug='acme-nt1')

    def test_degraded_component_appears_on_public_page(self):
        ComponentStatus.objects.create(
            nom='API', region='EU-West/Hetzner',
            statut=ComponentStatus.Statut.DEGRADED, company=None,
        )
        resp = self.client.get('/api/django/statuspage/public/')
        self.assertEqual(resp.status_code, 200)
        noms = {c['nom']: c['statut'] for c in resp.data['composants']}
        self.assertEqual(noms['API'], 'degraded')
        self.assertEqual(resp.data['overall_status'], 'degraded')

    def test_incident_with_updates_visible_publicly(self):
        incident = IncidentPublic.objects.create(
            titre='Latence API élevée', severite=IncidentPublic.Severite.MAJEURE,
            statut=IncidentPublic.Statut.RESOLVED,
            debute_le=timezone.now(), resolu_le=timezone.now(), company=None,
        )
        IncidentUpdate.objects.create(
            incident=incident, statut=IncidentPublic.Statut.INVESTIGATING,
            message='Investigation en cours.',
        )
        IncidentUpdate.objects.create(
            incident=incident, statut=IncidentPublic.Statut.RESOLVED,
            message='Résolu après redémarrage.',
        )
        resp = self.client.get('/api/django/statuspage/public/incidents/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['titre'], 'Latence API élevée')
        self.assertEqual(len(results[0]['updates']), 2)

    def test_public_endpoint_never_leaks_company_data(self):
        ComponentStatus.objects.create(
            nom='Composant privé', region='interne', company=self.company,
            statut=ComponentStatus.Statut.MAJOR_OUTAGE,
        )
        IncidentPublic.objects.create(
            titre='Incident société Acme', company=self.company,
            debute_le=timezone.now(),
        )
        resp = self.client.get('/api/django/statuspage/public/')
        noms = [c['nom'] for c in resp.data['composants']]
        self.assertNotIn('Composant privé', noms)

        resp2 = self.client.get('/api/django/statuspage/public/incidents/')
        results = resp2.data.get('results', resp2.data)
        titres = [r['titre'] for r in results]
        self.assertNotIn('Incident société Acme', titres)

    def test_public_status_response_is_cached_60_seconds(self):
        ComponentStatus.objects.create(
            nom='API', region='EU-West/Hetzner', company=None,
            statut=ComponentStatus.Statut.OPERATIONAL,
        )
        r1 = self.client.get('/api/django/statuspage/public/')
        # Un nouveau composant créé APRÈS le premier appel ne doit pas
        # apparaître avant l'expiration du cache (60s) — preuve du cache.
        ComponentStatus.objects.create(
            nom='PDF-devis', region='EU-West/Hetzner', company=None,
            statut=ComponentStatus.Statut.OPERATIONAL,
        )
        r2 = self.client.get('/api/django/statuspage/public/')
        self.assertEqual(
            len(r1.data['composants']), len(r2.data['composants']))


class RafraichirComposantsTaskTest(TestCase):
    """NTOBS1 — le job beat dérive le statut public depuis check_services()."""

    def test_beat_task_marks_component_degraded_when_probe_down(self):
        fake_services = [
            {'name': 'database', 'status': 'ok', 'detail': ''},
            {'name': 'cache', 'status': 'ok', 'detail': ''},
            {'name': 'storage', 'status': 'down', 'detail': 'MinIO injoignable'},
            {'name': 'broker', 'status': 'ok', 'detail': ''},
            {'name': 'queue', 'status': 'ok', 'detail': ''},
        ]
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                return_value=fake_services):
            maj = rafraichir_composants()
        self.assertGreater(maj, 0)
        stockage = ComponentStatus.objects.get(
            nom='Stockage documents', company=None)
        self.assertEqual(stockage.statut, ComponentStatus.Statut.MAJOR_OUTAGE)
        api = ComponentStatus.objects.get(nom='API', company=None)
        self.assertEqual(api.statut, ComponentStatus.Statut.OPERATIONAL)

    def test_beat_task_never_raises_when_check_services_fails(self):
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                side_effect=RuntimeError('boom')):
            maj = rafraichir_composants()
        self.assertEqual(maj, 0)
