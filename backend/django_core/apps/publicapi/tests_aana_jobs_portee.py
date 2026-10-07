"""AANA33 — ``/api/public/v1/jobs/`` borné à la clé ou au scope de l'entité.

Constat C-AANA-010 : n'importe quelle clé de la société (``read:stock``)
lisait le détail d'un export de leads créé par une autre clé, lien présigné
``resultat_url`` compris — un contournement complet du scope ``read:leads``.
Désormais une clé ne voit que ses jobs, ou ceux d'une entité dont elle porte
le scope de l'opération (``bulk_views.jobs_visibles_q``) ; sinon 404.

Vraie vue, vraie authentification par clé, vraie base ; seul le client MinIO
(frontière externe) est simulé pour signer le lien.

Run :
    python manage.py test apps.publicapi.tests_aana_jobs_portee -v2
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import ApiKey, BulkJob
from .portees import SCOPE_READ_LEADS, SCOPE_READ_STOCK, SCOPE_WRITE_LEADS


def _client(brute):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {brute}')
    return api


def _resultats(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class JobsPorteeTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana33-co', defaults={'nom': 'AANA33'})
        self.cle_leads, self.brute_leads = ApiKey.issue(
            company=self.co, label='leads', scopes=[SCOPE_READ_LEADS])
        self.cle_stock, self.brute_stock = ApiKey.issue(
            company=self.co, label='stock', scopes=[SCOPE_READ_STOCK])
        self.job = BulkJob.objects.create(
            company=self.co, api_key=self.cle_leads,
            type=BulkJob.TYPE_EXPORT, entite='leads', params={},
            statut=BulkJob.STATUT_TERMINE,
            resultat_file_key='exports/aana33/leads.csv')

    def _get(self, brute, url):
        from apps.records import storage
        with mock.patch.object(storage, 'get_minio_client') as client:
            client.return_value.generate_presigned_url.return_value = (
                'https://minio.example.test/leads.csv')
            return _client(brute).get(url)

    def test_autre_cle_404(self):
        resp = self._get(self.brute_stock, f'/api/public/v1/jobs/{self.job.id}/')
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('minio.example.test', resp.content.decode('utf-8'))

    def test_cle_creatrice_200_avec_lien(self):
        resp = self._get(self.brute_leads, f'/api/public/v1/jobs/{self.job.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['resultat_url'],
                         'https://minio.example.test/leads.csv')

    def test_la_liste_ne_montre_pas_le_job_d_une_autre_entite(self):
        resp = self._get(self.brute_stock, '/api/public/v1/jobs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [r['id'] for r in _resultats(resp)], [])

    def test_une_autre_cle_avec_le_scope_de_l_entite_le_voit(self):
        _cle, brute = ApiKey.issue(
            company=self.co, label='leads-2', scopes=[SCOPE_READ_LEADS])
        resp = self._get(brute, f'/api/public/v1/jobs/{self.job.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_le_scope_d_import_ne_voit_pas_l_export(self):
        _cle, brute = ApiKey.issue(
            company=self.co, label='ecriture', scopes=[SCOPE_WRITE_LEADS])
        resp = self._get(brute, f'/api/public/v1/jobs/{self.job.id}/')
        self.assertEqual(resp.status_code, 404)
