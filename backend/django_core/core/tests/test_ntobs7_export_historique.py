"""NTOBS7 — écran de téléchargement de l'export de réversibilité + historique."""
from importlib import import_module
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from core.export_registry import ExportReversibiliteRun
from core.tasks import export_reversibilite_tenant

Role = django_apps.get_model('roles', 'Role')

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

    def test_export_orphelin_passe_en_echec_et_previent(self):
        """ACEL11 — un export ou un job tué depuis plus de 30 min passe en
        échec par le balayage planifié, et son demandeur est prévenu ; un job
        récent reste en cours."""
        from datetime import timedelta

        from django.utils import timezone

        from core.models import BackgroundJob
        from core.tasks import balayer_travaux_orphelins_task

        user = User.objects.create_user(
            username='acel11', password='x', company=self.company)
        il_y_a_45 = timezone.now() - timedelta(minutes=45)
        run = ExportReversibiliteRun.objects.create(
            company=self.company, demande_par=user,
            statut=ExportReversibiliteRun.Statut.EN_COURS)
        vieux = BackgroundJob.objects.create(
            company=self.company, user=user, kind='export',
            statut=BackgroundJob.STATUT_RUNNING)
        recent = BackgroundJob.objects.create(
            company=self.company, user=user, kind='export',
            statut=BackgroundJob.STATUT_RUNNING)
        ExportReversibiliteRun.objects.filter(pk=run.pk).update(
            updated_at=il_y_a_45)
        BackgroundJob.objects.filter(pk=vieux.pk).update(updated_at=il_y_a_45)
        BackgroundJob.objects.filter(pk=recent.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5))

        balayer_travaux_orphelins_task()

        run.refresh_from_db()
        vieux.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(run.statut, ExportReversibiliteRun.Statut.ECHEC)
        self.assertEqual(vieux.statut, BackgroundJob.STATUT_FAILED)
        self.assertIn('interrompu', vieux.message_erreur)
        self.assertEqual(recent.statut, BackgroundJob.STATUT_RUNNING)
        Notification = django_apps.get_model('notifications', 'Notification')
        self.assertTrue(Notification.objects.filter(
            recipient=user, event_type='travail_de_fond_echoue').exists())


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
        # APUB1 — l'historique est réservé au Directeur / à l'Administrateur.
        directeur = User.objects.create_user(
            'directeur7h', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Directeur'))
        client_directeur = APIClient()
        client_directeur.force_authenticate(directeur)
        resp = client_directeur.get('/api/django/core/export-reversibilite/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_historique_refuse_aux_roles_livres_non_lanceurs(self):
        """APUB1 — Commercial et Commercial responsable livrés : 403, aucun
        jeton servi ; Directeur livré : 200 avec le jeton du run prêt."""
        registre = import_module('apps.roles.permissions_registre')
        COMMERCIAL_PERMISSIONS = registre.COMMERCIAL_PERMISSIONS
        COMMERCIAL_RESP_PERMISSIONS = registre.COMMERCIAL_RESP_PERMISSIONS
        DIRECTEUR_PERMISSIONS = registre.DIRECTEUR_PERMISSIONS
        ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.PRET,
            token='jeton-apub1')
        url = '/api/django/core/export-reversibilite/historique/'
        for nom, perms, attendu in (
                ('Commercial', COMMERCIAL_PERMISSIONS, 403),
                ('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS, 403),
                ('Directeur', DIRECTEUR_PERMISSIONS, 200)):
            user = User.objects.create_user(
                f'apub1-{nom}', password='x', company=self.company,
                role=Role.objects.create(
                    company=self.company, nom=nom, permissions=list(perms)))
            api = APIClient()
            api.force_authenticate(user)
            resp = api.get(url)
            with self.subTest(role=nom):
                self.assertEqual(resp.status_code, attendu, resp.data)
                if attendu == 403:
                    self.assertNotIn('jeton-apub1', str(resp.content))
                else:
                    self.assertEqual(resp.data[0]['token'], 'jeton-apub1')

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

    def test_couper_le_lien_rend_le_telechargement_404(self):
        """APUB2 — le Directeur coupe le lien d'un export « prêt » : lien
        inactif, run « Expiré », téléchargement 404 ; Commercial responsable
        livré : 403 sans écriture ; second POST identique ; autre société 404."""
        registre = import_module('apps.roles.permissions_registre')
        COMMERCIAL_RESP_PERMISSIONS = registre.COMMERCIAL_RESP_PERMISSIONS
        DIRECTEUR_PERMISSIONS = registre.DIRECTEUR_PERMISSIONS
        from core import signed_download
        from core.tasks import REVERSIBILITE_BUCKET

        def compte(nom, perms):
            user = User.objects.create_user(
                f'apub2-{nom}', password='x', company=self.company,
                role=Role.objects.create(
                    company=self.company, nom=nom, permissions=list(perms)))
            api = APIClient()
            api.force_authenticate(user)
            return api

        lien = signed_download.creer_lien(
            self.company, REVERSIBILITE_BUCKET, 'export.zip')
        run = ExportReversibiliteRun.objects.create(
            company=self.company, statut=ExportReversibiliteRun.Statut.PRET,
            token=lien.token)
        url = f'/api/django/core/export-reversibilite/{run.id}/couper-lien/'
        resp = compte('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS).post(url)
        self.assertEqual(resp.status_code, 403, resp.data)
        lien.refresh_from_db()
        run.refresh_from_db()
        self.assertTrue(lien.actif)
        self.assertEqual(run.statut, ExportReversibiliteRun.Statut.PRET)

        directeur = compte('Directeur', DIRECTEUR_PERMISSIONS)
        for _ in range(2):  # idempotent : le second POST rend la même chose
            resp = directeur.post(url)
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['statut'], 'expire')
        lien.refresh_from_db()
        run.refresh_from_db()
        self.assertFalse(lien.actif)
        self.assertEqual(run.statut, ExportReversibiliteRun.Statut.EXPIRE)
        resp = APIClient().get(
            f'/api/django/core/export-reversibilite/telecharger/{lien.token}/')
        self.assertEqual(resp.status_code, 404)

        autre = Company.objects.create(nom='Autre', slug='autre-apub2')
        run_autre = ExportReversibiliteRun.objects.create(
            company=autre, statut=ExportReversibiliteRun.Statut.PRET, token='x')
        resp = directeur.post(
            f'/api/django/core/export-reversibilite/{run_autre.id}/couper-lien/')
        self.assertEqual(resp.status_code, 404)
