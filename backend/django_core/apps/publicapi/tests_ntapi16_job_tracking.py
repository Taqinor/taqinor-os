"""NTAPI16 — Suivi de job `GET /api/public/v1/jobs/<id>/` + liste paginée.

Couvre : statut/progression %/compteurs/liens, `Retry-After` conseillé tant
que `en_cours`, liste paginée, cross-tenant impossible (déjà couvert côté
NTAPI14 pour le `retrieve` — ici : la `list` ne fuite jamais un job d'une
autre société, et les liens résultat/erreurs n'apparaissent qu'au bon moment).
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .portees import SCOPE_READ_LEADS
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

        resp = _client(self.raw_a).get('/api/public/v1/jobs/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)

    def test_detail_progression_and_links(self):
        job = BulkJob.objects.create(
            company=self.co_a, api_key=self.api_key_a, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={}, total=10, traites=5, statut=BulkJob.STATUT_EN_COURS)

        resp = _client(self.raw_a).get(f'/api/public/v1/jobs/{job.id}/')

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
            resp = _client(self.raw_a).get(f'/api/public/v1/jobs/{job.id}/')

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Retry-After', resp.headers)
        # APRF46 — chemin de l'API publique, jamais l'URL MinIO présignée.
        self.assertEqual(resp.data['resultat_url'], f'/api/public/v1/jobs/{job.id}/resultat/')

    def test_livrable_servi_par_l_api_publique(self):
        """APRF46 (C-APRF-OPT1-000) — `resultat_url`/`erreurs_url` sont des
        chemins de l'API publique : 200 + octets + attachment à la clé
        créatrice, 404 à une clé `read:stock` ; job non terminé ⇒ null + 404."""
        import io

        from apps.records import storage

        from .portees import SCOPE_READ_STOCK
        depot = {'exports/1/leads.csv': b'id\n1\n', 'exports/1/erreurs.csv': b'ligne\n2\n',
                 'exports/1/partiel.csv': b'id\n'}
        job = BulkJob.objects.create(
            company=self.co_a, api_key=self.api_key_a, type=BulkJob.TYPE_EXPORT, entite='leads',
            params={}, statut=BulkJob.STATUT_TERMINE, resultat_file_key='exports/1/leads.csv',
            erreurs_file_key='exports/1/erreurs.csv')
        en_cours = BulkJob.objects.create(
            company=self.co_a, api_key=self.api_key_a, type=BulkJob.TYPE_EXPORT, entite='leads',
            params={}, statut=BulkJob.STATUT_EN_COURS, resultat_file_key='exports/1/partiel.csv')
        _cle, brute_stock = _key(self.co_a, scopes=[SCOPE_READ_STOCK])
        createur, autre = _client(self.raw_a), _client(brute_stock)
        with mock.patch.object(storage, 'get_minio_client') as get_client:
            get_client.return_value.get_object.side_effect = (
                lambda Bucket, Key: {'Body': io.BytesIO(depot[Key])})
            get_client.return_value.generate_presigned_url.return_value = 'https://minio/x'
            detail = createur.get(f'/api/public/v1/jobs/{job.id}/').data
            self.assertEqual(detail['resultat_url'], f'/api/public/v1/jobs/{job.id}/resultat/')
            self.assertEqual(detail['erreurs_url'], f'/api/public/v1/jobs/{job.id}/erreurs/')
            for url, cle in ((detail['resultat_url'], 'exports/1/leads.csv'),
                             (detail['erreurs_url'], 'exports/1/erreurs.csv')):
                resp = createur.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.content, depot[cle])
                self.assertTrue(resp['Content-Disposition'].startswith('attachment'))
                self.assertEqual(autre.get(url).status_code, 404)
            self.assertIsNone(createur.get(f'/api/public/v1/jobs/{en_cours.id}/').data['resultat_url'])
            self.assertEqual(createur.get(f'/api/public/v1/jobs/{en_cours.id}/resultat/').status_code, 404)

    def test_cross_tenant_job_is_404_not_leaked(self):
        job_b = BulkJob.objects.create(
            company=self.co_b, api_key=self.api_key_b, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={})
        resp = _client(self.raw_a).get(f'/api/public/v1/jobs/{job_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_no_api_key_is_401(self):
        resp = APIClient().get('/api/public/v1/jobs/')
        self.assertEqual(resp.status_code, 401)

    def test_jobs_endpoint_accepts_any_scope_not_only_read_leads(self):
        # Un job n'appartient pas à UN scope métier — toute clé valide de la
        # société peut suivre SES jobs, quel que soit le scope qu'elle porte.
        from .portees import SCOPE_READ_STOCK
        api_key, raw = _key(self.co_a, scopes=[SCOPE_READ_STOCK])
        BulkJob.objects.create(
            company=self.co_a, api_key=api_key, type=BulkJob.TYPE_EXPORT,
            entite='produits', params={})
        resp = _client(raw).get('/api/public/v1/jobs/')
        self.assertEqual(resp.status_code, 200)
