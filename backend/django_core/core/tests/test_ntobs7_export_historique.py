"""NTOBS7 — écran de téléchargement de l'export de réversibilité + historique."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role

from core.export_registry import ExportReversibiliteRun
from core.tasks import export_reversibilite_tenant

User = get_user_model()


class ExportRunLifecycleTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs7')

    def test_run_progresses_from_en_cours_to_pret(self):
        run = ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.EN_COURS)
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            result = export_reversibilite_tenant(self.company.id, run_id=run.id)
        run.refresh_from_db()
        self.assertTrue(result['ok'])
        self.assertEqual(run.statut, ExportReversibiliteRun.Statut.PRET)
        self.assertEqual(run.token, result['token'])
        self.assertIsNotNone(run.expire_le)
        self.assertIsNotNone(run.taille_octets)

    def test_run_marked_echec_on_minio_failure(self):
        run = ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.EN_COURS)
        with mock.patch(
                'core.backup._minio_client',
                side_effect=RuntimeError('minio down')):
            result = export_reversibilite_tenant(self.company.id, run_id=run.id)
        run.refresh_from_db()
        self.assertFalse(result['ok'])
        self.assertEqual(run.statut, ExportReversibiliteRun.Statut.ECHEC)

    def test_missing_run_id_never_crashes_ntobs6_alone(self):
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            result = export_reversibilite_tenant(self.company.id)
        self.assertTrue(result['ok'])


class HistoriqueEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs7b')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_history_is_scoped_to_company(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs7b')
        ExportReversibiliteRun.objects.create(company=self.company)
        ExportReversibiliteRun.objects.create(company=autre)
        resp = self.client.get('/api/django/core/export-reversibilite/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_declencher_creates_a_pending_history_row(self):
        role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        directeur = User.objects.create_user(
            'directeur7', password='x', company=self.company,
            role=role_directeur)
        client_directeur = APIClient()
        client_directeur.force_authenticate(directeur)
        with mock.patch('core.tasks.export_reversibilite_tenant.delay') as delay:
            resp = client_directeur.post('/api/django/core/export-reversibilite/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['statut'], 'en_cours')
        self.assertTrue(delay.called)
        _args, kwargs = delay.call_args
        self.assertEqual(
            ExportReversibiliteRun.objects.filter(company=self.company).count(), 1)
        self.assertIn('run_id', kwargs)
