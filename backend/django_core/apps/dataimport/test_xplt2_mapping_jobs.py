"""XPLT2 — mappings d'import sauvegardés + journal ImportJob/ImportJobRow +
CSV des lignes en échec + choix commit partiel vs rollback atomique."""
from apps.crm.models import Lead

from .models import ImportJob, ImportJobRow, ImportMapping
from .tests import ImportBase


class TestSavedMapping(ImportBase):
    def test_save_and_reapply_mapping_at_dry_run(self):
        resp = self.api.post('/api/django/imports/mapping/', {
            'target': 'leads', 'nom': 'Export CRM X',
            'mapping': {'Full Name': 'nom', 'Mail': 'email'},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(ImportMapping.objects.filter(
            company=self.company, entity='leads', nom='Export CRM X').exists())

        # Colonnes que le mapping AUTOMATIQUE ne connaît pas du tout — seul le
        # mapping sauvegardé permet de les rapprocher.
        f = self._csv('Full Name,Mail\nKarim,karim@x.ma\n')
        resp2 = self.api.post('/api/django/imports/dry-run/', {
            'file': f, 'target': 'leads', 'mapping': 'Export CRM X',
        }, format='multipart')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['mapping']['Full Name'], 'nom')
        self.assertEqual(resp2.data['mapping']['Mail'], 'email')
        self.assertEqual(resp2.data['apercu'][0]['nom'], 'Karim')

    def test_save_mapping_requires_dict(self):
        resp = self.api.post('/api/django/imports/mapping/', {
            'target': 'leads', 'nom': 'Bad', 'mapping': 'not-a-dict',
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class TestImportJobLog(ImportBase):
    def test_commit_creates_job_with_row_errors(self):
        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        f = self._csv('Nom,Email\n'
                      'Alaoui,new@x.ma\n'
                      'Doublon,dup@x.ma\n'
                      ',\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        job_id = resp.data['job_id']
        job = ImportJob.objects.get(pk=job_id, company=self.company)
        self.assertEqual(job.statut, ImportJob.Statut.PARTIEL)
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.error_count, 2)
        rows = list(job.rows.order_by('ligne'))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].statut, ImportJobRow.Statut.OK)
        self.assertEqual(rows[1].statut, ImportJobRow.Statut.ERREUR)
        self.assertIn('doublon', rows[1].motif)
        self.assertEqual(rows[1].donnees.get('Email'), 'dup@x.ma')

    def test_erreurs_csv_contains_only_failed_rows_and_is_reimportable(self):
        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        f = self._csv('Nom,Email\n'
                      'Alaoui,new@x.ma\n'
                      'Doublon,dup@x.ma\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        job_id = resp.data['job_id']

        csv_resp = self.api.get(f'/api/django/imports/jobs/{job_id}/erreurs.csv')
        self.assertEqual(csv_resp.status_code, 200)
        body = csv_resp.content.decode('utf-8')
        self.assertIn('dup@x.ma', body)
        self.assertNotIn('new@x.ma', body)  # la ligne réussie n'apparaît pas

        # Le CSV d'échecs se ré-importe : on retire juste la colonne _motif
        # avant de le renvoyer au dry-run (comportement attendu côté client).
        reimport = self.api.post('/api/django/imports/dry-run/', {
            'file': self._csv(body), 'target': 'leads',
        }, format='multipart')
        self.assertEqual(reimport.status_code, 200, reimport.data)
        self.assertEqual(reimport.data['mapping'].get('Nom'), 'nom')

    def test_job_isolated_per_company(self):
        f = self._csv('Nom,Email\nA,a@a.ma\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        job_id = resp.data['job_id']

        from authentication.models import Company
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        User = get_user_model()
        other = Company.objects.create(slug='imp-co-3', nom='Imp Co 3')
        other_user = User.objects.create_user(
            username='other_u', password='x', role_legacy='responsable',
            company=other)
        other_api = APIClient()
        other_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(other_user)}')

        resp2 = other_api.get(f'/api/django/imports/jobs/{job_id}/erreurs.csv')
        self.assertEqual(resp2.status_code, 404)


class TestRollbackChoice(ImportBase):
    def test_default_partial_commit_keeps_successful_rows(self):
        f = self._csv('Nom,Email\nOk,ok@x.ma\n,\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(Lead.objects.filter(
            company=self.company, email='ok@x.ma').exists())

    def test_rollback_on_error_discards_everything(self):
        f = self._csv('Nom,Email\nOk,ok2@x.ma\n,\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'leads', 'rollback_on_error': 'true',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(resp.data['statut'], ImportJob.Statut.ECHEC)
        self.assertFalse(Lead.objects.filter(
            company=self.company, email='ok2@x.ma').exists())
        job = ImportJob.objects.get(pk=resp.data['job_id'])
        self.assertEqual(job.statut, ImportJob.Statut.ECHEC)
        self.assertEqual(job.created_count, 0)
