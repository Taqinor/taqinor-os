"""Tests FG383 — extraits planifiés vers SFTP/S3 (gated).

Couvre :
  * rendu CSV depuis un dataset (FG382) ;
  * runner no-op propre quand la destination n'est pas configurée ;
  * connecteurs SFTP/S3 enregistrés + non configurés → aucun transfert ;
  * écriture réservée admin/responsable ; lecture pour tout authentifié ;
  * company imposée côté serveur ; isolation société ;
  * découplage : dataset enregistré sur un modèle de FONDATION (Company).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer, scheduled_export
from core.integrations import get_provider_class
from core.models import ScheduledExport
from core.views import ScheduledExportViewSet

User = get_user_model()


def _companies_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class ScheduledExportEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def setUp(self):
        data_explorer.register_dataset(
            'societes', 'Sociétés', ['id', 'nom'], _companies_dataset)

    def test_destinations_registered(self):
        self.assertIsNotNone(
            get_provider_class(scheduled_export.TYPE_EXPORT_DEST, 'sftp'))
        self.assertIsNotNone(
            get_provider_class(scheduled_export.TYPE_EXPORT_DEST, 's3'))

    def test_rendre_extrait_csv(self):
        exp = ScheduledExport.objects.create(
            company=self.company, titre='ACME export', dataset='societes',
            spec={'select': ['nom']}, format='csv', destination='sftp')
        filename, data, content_type = scheduled_export.rendre_extrait(exp)
        self.assertTrue(filename.endswith('.csv'))
        self.assertEqual(content_type, 'text/csv')
        self.assertIn(b'nom', data)
        self.assertIn(b'ACME', data)

    def test_executer_noop_when_unconfigured(self):
        exp = ScheduledExport.objects.create(
            company=self.company, titre='X', dataset='societes',
            spec={'select': ['nom']}, format='csv', destination='s3')
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'non_configure')
        self.assertIsNotNone(exp.derniere_execution_le)


class ScheduledExportViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='exp_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='exp_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_requires_admin_tier(self):
        body = {'titre': 'E', 'dataset': 'societes', 'destination': 'sftp'}
        req = self.factory.post('/scheduled-exports/', body, format='json')
        force_authenticate(req, user=self.user)
        resp = ScheduledExportViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_imposes_company(self):
        body = {'titre': 'E', 'dataset': 'societes', 'destination': 'sftp'}
        req = self.factory.post('/scheduled-exports/', body, format='json')
        force_authenticate(req, user=self.admin)
        resp = ScheduledExportViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        exp = ScheduledExport.objects.get(pk=resp.data['id'])
        self.assertEqual(exp.company, self.company)

    def test_company_isolation_on_list(self):
        ScheduledExport.objects.create(
            company=self.other, titre='Autre', dataset='x', destination='s3')
        req = self.factory.get('/scheduled-exports/')
        force_authenticate(req, user=self.user)
        resp = ScheduledExportViewSet.as_view({'get': 'list'})(req)
        titres = {row['titre'] for row in resp.data}
        self.assertNotIn('Autre', titres)
