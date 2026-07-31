"""NTAPI16 — Suivi de job `GET /api/public/jobs/<id>/` + liste paginée.

Couvre : statut/progression %/compteurs/liens, `Retry-After` conseillé tant
que `en_cours`, liste paginée, cross-tenant impossible (déjà couvert côté
NTAPI14 pour le `retrieve` — ici : la `list` ne fuite jamais un job d'une
autre société, et les liens résultat/erreurs n'apparaissent qu'au bon moment).
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .constants import SCOPE_READ_LEADS
from .models import ApiKey, BulkJob


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key(company, scopes=None):
    return ApiKey.issue(company=company, label='k', scopes=scopes or [SCOPE_READ_LEADS])


def _client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi16JobTrackingTests(TestCase):
    def setUp(self):
        self.co_a = _company('ntapi16-a', 'A')
        self.co_b = _company('ntapi16-b', 'B')
        self.api_key_a, self.raw_a = _key(self.co_a)
        self.api_key_b, self.raw_b = _key(self.co_b)

    def test_list_only_shows_own_company_jobs(self):
        BulkJob.objects.create(
            company=self.co_a, api_key=self.api_key_a, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={})
        BulkJob.objects.create(
            company=self.co_b, api_key=self.api_key_b, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={})

        resp = _client(self.raw_a).get('/api/public/jobs/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)

    def test_detail_progression_and_links(self):
        job = BulkJob.objects.create(
            company=self.co_a, api_key=self.api_key_a, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={}, total=10, traites=5, statut=BulkJob.STATUT_EN_COURS)

        resp = _client(self.raw_a).get(f'/api/public/jobs/{job.id}/')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['progression_pct'], 50)
        self.assertIsNone(resp.data['resultat_url'])  # pas encore terminé
        self.assertEqual(resp.headers.get('Retry-After'), '3')

    def test_no_retry_after_once_termine(self):
        job = BulkJob.objects.create(
            company=self.co_a, api_key=self.api_key_a, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={}, statut=BulkJob.STATUT_TERMINE,
            resultat_file_key='exports/1/1.csv')
        from apps.records import storage
        with mock.patch.object(
                storage, 'get_minio_client') as get_client:
            get_client.return_value.generate_presigned_url.return_value = (
                'https://minio/x')
            resp = _client(self.raw_a).get(f'/api/public/jobs/{job.id}/')

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Retry-After', resp.headers)
        self.assertEqual(resp.data['resultat_url'], 'https://minio/x')

    def test_cross_tenant_job_is_404_not_leaked(self):
        job_b = BulkJob.objects.create(
            company=self.co_b, api_key=self.api_key_b, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={})
        resp = _client(self.raw_a).get(f'/api/public/jobs/{job_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_no_api_key_is_401(self):
        resp = APIClient().get('/api/public/jobs/')
        self.assertEqual(resp.status_code, 401)

    def test_jobs_endpoint_accepts_any_scope_not_only_read_leads(self):
        # Un job n'appartient pas à UN scope métier — toute clé valide de la
        # société peut suivre SES jobs, quel que soit le scope qu'elle porte.
        from .constants import SCOPE_READ_STOCK
        api_key, raw = _key(self.co_a, scopes=[SCOPE_READ_STOCK])
        BulkJob.objects.create(
            company=self.co_a, api_key=api_key, type=BulkJob.TYPE_EXPORT,
            entite='produits', params={})
        resp = _client(raw).get('/api/public/jobs/')
        self.assertEqual(resp.status_code, 200)
