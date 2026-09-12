"""NTOBS3 — rapport SLA mensuel par tenant (uptime mesuré + P95 + export PDF)."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from django.apps import apps as django_apps

from authentication.models import Company

from core import metrics as metrics_infra
from core.sla import SlaSnapshot, generer_snapshot_societe, uptime_pct_periode

User = get_user_model()
# Résolu par nom (jamais un import statique d'apps.statuspage) : core reste
# une couche de base (contrat import-linter core-foundation-is-a-base-layer),
# même en test — même patron que core.tests.test_rls_cross_tenant_denial
# (AUD422, ".importlinter").
IncidentPublic = django_apps.get_model('statuspage', 'IncidentPublic')


class UptimePctPeriodeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs3')
        self.periode = datetime.date(2026, 6, 1)

    def _aware(self, *args):
        return timezone.make_aware(datetime.datetime(*args))

    def test_full_month_with_no_incident_is_100_percent(self):
        self.assertEqual(uptime_pct_periode(self.company, self.periode), 100.0)

    def test_critical_incident_reduces_uptime(self):
        IncidentPublic.objects.create(
            titre='Panne totale', severite=IncidentPublic.Severite.CRITIQUE,
            statut=IncidentPublic.Statut.RESOLVED, company=None,
            debute_le=self._aware(2026, 6, 10, 0, 0),
            resolu_le=self._aware(2026, 6, 10, 6, 0),  # 6h d'arrêt critique
        )
        uptime = uptime_pct_periode(self.company, self.periode)
        self.assertLess(uptime, 100.0)
        # 6h sur un mois de 30 jours (720h) ~ 99.17%
        self.assertGreater(uptime, 99.0)

    def test_minor_incident_does_not_reduce_uptime(self):
        IncidentPublic.objects.create(
            titre='Ralentissement mineur', severite=IncidentPublic.Severite.MINEURE,
            statut=IncidentPublic.Statut.RESOLVED, company=None,
            debute_le=self._aware(2026, 6, 10, 0, 0),
            resolu_le=self._aware(2026, 6, 10, 6, 0),
        )
        self.assertEqual(uptime_pct_periode(self.company, self.periode), 100.0)

    def test_incident_of_another_company_does_not_affect_uptime(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs3')
        IncidentPublic.objects.create(
            titre='Panne société tierce',
            severite=IncidentPublic.Severite.CRITIQUE,
            statut=IncidentPublic.Statut.RESOLVED, company=autre,
            debute_le=self._aware(2026, 6, 10, 0, 0),
            resolu_le=self._aware(2026, 6, 10, 6, 0),
        )
        self.assertEqual(uptime_pct_periode(self.company, self.periode), 100.0)


class GenererSnapshotSocieteTest(TestCase):
    def setUp(self):
        # ``core.metrics._http_by_tenant`` est un registre PROCESS-LOCAL (pas
        # une table) : toute requete API d'un AUTRE test du meme processus y
        # laisse un echantillon, sous un label derive de l'id societe — ou
        # sous le label de repli « other » une fois le plafond de cardinalite
        # atteint. Sans purge, « p95 sans mesure » lisait la mesure d'un
        # voisin (100 ms observes en CI). Meme purge que P95LatencyMsTest.
        metrics_infra._http_by_tenant.clear()
        metrics_infra._http_real_companies.clear()
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs3b')

    def test_generates_and_upserts_snapshot(self):
        periode = datetime.date(2026, 6, 1)
        snap1 = generer_snapshot_societe(self.company, periode)
        self.assertEqual(SlaSnapshot.objects.filter(company=self.company).count(), 1)
        snap2 = generer_snapshot_societe(self.company, periode)
        self.assertEqual(snap1.pk, snap2.pk)
        self.assertEqual(SlaSnapshot.objects.filter(company=self.company).count(), 1)

    def test_p95_is_none_without_measurement(self):
        periode = datetime.date(2026, 6, 1)
        snap = generer_snapshot_societe(self.company, periode)
        self.assertIsNone(snap.latence_p95_ms)


class P95LatencyMsTest(TestCase):
    def setUp(self):
        metrics_infra._http_by_tenant.clear()
        metrics_infra._http_real_companies.clear()

    def test_none_without_samples(self):
        self.assertIsNone(metrics_infra.p95_latency_ms(999))

    def test_p95_bucket_from_recorded_requests(self):
        for _ in range(19):
            metrics_infra.record_http_request(42, 200, 40)  # 0.04s -> bucket 0.05
        metrics_infra.record_http_request(42, 200, 3000)  # 3s -> bucket 5.0
        p95 = metrics_infra.p95_latency_ms(42)
        self.assertIsNotNone(p95)
        self.assertGreaterEqual(p95, 50)


class SlaEndpointsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs3c')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_is_scoped_to_company(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs3c')
        generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        generer_snapshot_societe(autre, datetime.date(2026, 6, 1))
        resp = self.client.get('/api/django/core/sla/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_export_pdf_404_without_snapshot(self):
        resp = self.client.get('/api/django/core/sla/2026-06/export-pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_export_pdf_returns_pdf_bytes(self):
        generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        with mock.patch('core.pdf.render_pdf', return_value=b'%PDF-fake'):
            resp = self.client.get('/api/django/core/sla/2026-06/export-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
