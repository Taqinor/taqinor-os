"""NTOBS18 — registre de fiabilité (PDF interne consolidé par société/période)."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.roles.models import Role
from django.apps import apps as django_apps
from authentication.models import Company
from core.models import BackupRun
from core.pdf_registre_fiabilite import _incidents, _snapshots
from core.sla import generer_snapshot_societe

# Pas d'import statique d'une app domaine sous core (contrat import-linter M3)
IncidentPublic = django_apps.get_model('statuspage', 'IncidentPublic')

User = get_user_model()


class RegistreFiabiliteDataTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs18-acme')

    def test_snapshots_scoped_to_company_and_range(self):
        autre = Company.objects.create(nom='Autre', slug='ntobs18-autre')
        generer_snapshot_societe(self.company, datetime.date(2026, 5, 1))
        generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        generer_snapshot_societe(autre, datetime.date(2026, 6, 1))
        rows = _snapshots(
            self.company, datetime.date(2026, 6, 1), datetime.date(2026, 6, 1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].company_id, self.company.id)

    def test_incidents_include_system_wide_and_company_specific(self):
        now = timezone.now()
        IncidentPublic.objects.create(
            titre='Système', company=None, debute_le=now)
        IncidentPublic.objects.create(
            titre='Autre société', company=Company.objects.create(
                nom='X', slug='ntobs18-x'), debute_le=now)
        rows = _incidents(self.company, now.date(), now.date())
        titres = [i.titre for i in rows]
        self.assertIn('Système', titres)
        self.assertNotIn('Autre société', titres)


class RegistreFiabiliteEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs18-b')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial')
        self.directeur = User.objects.create_user(
            'directeur18', password='x', company=self.company,
            role=self.role_directeur)
        self.commercial = User.objects.create_user(
            'commercial18', password='x', company=self.company,
            role=self.role_commercial)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_directeur_gets_pdf(self):
        generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        BackupRun.objects.create(
            company=None, kind=BackupRun.KIND_DB_DUMP,
            mode=BackupRun.MODE_PLANIFIE, statut=BackupRun.STATUT_TERMINE)
        with mock.patch('core.pdf.render_pdf', return_value=b'%PDF-fake'):
            resp = self._client(self.directeur).get(
                '/api/django/core/registre-fiabilite/export-pdf/'
                '?periode_debut=2026-06&periode_fin=2026-06')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_non_directeur_forbidden(self):
        resp = self._client(self.commercial).get(
            '/api/django/core/registre-fiabilite/export-pdf/'
            '?periode_debut=2026-06&periode_fin=2026-06')
        self.assertEqual(resp.status_code, 403)

    def test_invalid_periode_format_rejected(self):
        resp = self._client(self.directeur).get(
            '/api/django/core/registre-fiabilite/export-pdf/'
            '?periode_debut=bad&periode_fin=2026-06')
        self.assertEqual(resp.status_code, 400)

    def test_fin_before_debut_rejected(self):
        resp = self._client(self.directeur).get(
            '/api/django/core/registre-fiabilite/export-pdf/'
            '?periode_debut=2026-06&periode_fin=2026-01')
        self.assertEqual(resp.status_code, 400)
