"""Tests FG395 — sauvegarde/restauration en libre-service.

Couvre :
  * la sauvegarde produit un manifeste (compte de lignes par dataset) ;
  * création réservée au palier admin/responsable + company/declenche_par imposés ;
  * restauration sans artefact = tracée non_configure (jamais d'écriture aveugle) ;
  * isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import backup, data_explorer
from core.models import BackupRun
from core.views import BackupRunViewSet

User = get_user_model()


class BackupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='bk_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='bk_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()
        # Dataset bidon enregistré pour le manifeste (queryset scopé société).
        data_explorer.register_dataset(
            'companies_probe', 'Sociétés (sonde)', ['id'],
            lambda company, user: Company.objects.filter(pk=company.pk))

    def _create(self, user, body):
        req = self.factory.post('/sauvegardes/', body, format='json')
        force_authenticate(req, user=user)
        return BackupRunViewSet.as_view({'post': 'create'})(req)

    def test_backup_produces_manifest(self):
        resp = self._create(self.admin, {'kind': 'export',
                                         'datasets': ['companies_probe']})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        run = BackupRun.objects.get(pk=resp.data['id'])
        self.assertEqual(run.statut, BackupRun.STATUT_TERMINE)
        self.assertEqual(run.company, self.company)
        self.assertEqual(run.declenche_par, self.admin)
        self.assertEqual(run.manifest['total_lignes'], 1)

    def test_create_requires_admin_tier(self):
        resp = self._create(self.user, {'kind': 'export'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_not_from_body(self):
        resp = self._create(self.admin, {'kind': 'export',
                                         'company': self.other.pk})
        run = BackupRun.objects.get(pk=resp.data['id'])
        self.assertEqual(run.company, self.company)

    def test_restore_without_artifact_is_non_configure(self):
        run = BackupRun.objects.create(
            company=self.company, kind=BackupRun.KIND_RESTORE)
        backup.executer_restauration(run)
        run.refresh_from_db()
        self.assertEqual(run.statut, BackupRun.STATUT_NON_CONFIGURE)

    def test_manifest_helper_scopes_company(self):
        manifest = backup.construire_manifeste(self.company,
                                               datasets=['companies_probe'])
        self.assertEqual(manifest['total_lignes'], 1)
