"""NTOBS5 — écran self-service « Sauvegardes » pour l'admin tenant (lecture
seule des BackupRun déjà produits, jamais un nouveau moteur)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.parametres.models import CompanyProfile

from core.backup import resume_sauvegardes
from core.models import BackupRun

User = get_user_model()


class ResumeSauvegardesTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs5')

    def test_empty_state_never_invents_a_date(self):
        resume = resume_sauvegardes(self.company)
        self.assertIsNone(resume['derniere_sauvegarde'])
        self.assertIsNone(resume['dernier_drill'])

    def test_finds_latest_successful_export_for_company(self):
        BackupRun.objects.create(
            company=self.company, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_TERMINE,
            termine_le=timezone.now())
        resume = resume_sauvegardes(self.company)
        self.assertIsNotNone(resume['derniere_sauvegarde'])
        self.assertEqual(resume['derniere_sauvegarde']['statut'], 'termine')

    def test_system_wide_db_dump_counts_for_every_company(self):
        BackupRun.objects.create(
            company=None, kind=BackupRun.KIND_DB_DUMP,
            statut=BackupRun.STATUT_TERMINE, termine_le=timezone.now())
        resume = resume_sauvegardes(self.company)
        self.assertIsNotNone(resume['derniere_sauvegarde'])

    def test_another_companys_export_never_counts(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntobs5')
        BackupRun.objects.create(
            company=autre, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_TERMINE, termine_le=timezone.now())
        resume = resume_sauvegardes(self.company)
        self.assertIsNone(resume['derniere_sauvegarde'])

    def test_failed_export_is_never_reported_as_last_success(self):
        BackupRun.objects.create(
            company=self.company, kind=BackupRun.KIND_EXPORT,
            statut=BackupRun.STATUT_ECHEC, termine_le=timezone.now())
        resume = resume_sauvegardes(self.company)
        self.assertIsNone(resume['derniere_sauvegarde'])

    def test_reads_rto_from_company_profile(self):
        CompanyProfile.objects.create(company=self.company, rto_annonce_heures=12)
        resume = resume_sauvegardes(self.company)
        self.assertEqual(resume['rto_annonce_heures'], 12)

    def test_drill_reports_its_own_status_even_if_failed(self):
        BackupRun.objects.create(
            company=None, kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_ECHEC, termine_le=timezone.now())
        resume = resume_sauvegardes(self.company)
        self.assertIsNotNone(resume['dernier_drill'])
        self.assertEqual(resume['dernier_drill']['statut'], 'echec')


class MesSauvegardesEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs5b')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_endpoint_returns_scoped_resume(self):
        resp = self.client.get('/api/django/core/mes-sauvegardes/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('derniere_sauvegarde', resp.data)
        self.assertIn('dernier_drill', resp.data)
        self.assertIn('rpo_planifie', resp.data)

    def test_requires_authentication(self):
        anon = APIClient()
        resp = anon.get('/api/django/core/mes-sauvegardes/')
        self.assertEqual(resp.status_code, 401)
