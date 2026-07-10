"""SCA41 — exports xlsx asynchrones au-delà d'un seuil (pilote NTPLT29/30).

Couvre :
  1. Sous le seuil → chemin synchrone INCHANGÉ (200 + content-type xlsx,
     réponse pièce jointe, aucune tâche Celery) ;
  2. Au-delà du seuil → 202 + job_id + status_url ; la tâche construit le MÊME
     classeur (réutilise le builder synchrone → octets identiques) et l'upload
     dans MinIO sous une clé PRÉFIXÉE SOCIÉTÉ (motif ERR75) ;
  3. Le endpoint de statut est borné société : le job d'une autre société
     renvoie 404 (jamais visible) ; une fois prêt, il renvoie une URL de
     téléchargement pré-signée.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture
from apps.ventes import exports as exports_mod
from apps.ventes import tasks as tasks_mod

User = get_user_model()
JOURNAL_URL = '/api/django/ventes/journal-ventes/'
COMPTA_URL = '/api/django/ventes/export-comptable/'
XLSX_CT = ('application/vnd.openxmlformats-officedocument'
           '.spreadsheetml.sheet')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _FakeMinio:
    """Capture put_object / generate_presigned_url sans MinIO réel."""

    def __init__(self):
        self.puts = []

    def put_object(self, Bucket, Key, Body, ContentType):
        self.puts.append({'Bucket': Bucket, 'Key': Key,
                          'Body': Body, 'ContentType': ContentType})

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f'http://signed/{Params["Key"]}'


class Sca41AsyncExportTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='sca41-co', nom='SCA41 Co')
        self.user = User.objects.create_user(
            username='sca41_user', password='x',
            role_legacy='responsable', company=self.co)
        self.api = _auth(self.user)
        self.cli = Client.objects.create(
            company=self.co, nom='C', prenom='SCA41',
            email='sca41@example.invalid')

    def _facture(self, ref):
        f = Facture.objects.create(
            company=self.co, client=self.cli, reference=ref,
            statut='emise', taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), date_echeance=date(2026, 1, 31))
        # date_emission est auto_now_add (posé à aujourd'hui) — on le force en
        # janvier 2026 pour que le filtre de période ?month=2026-01 le capte.
        Facture.objects.filter(pk=f.pk).update(date_emission=date(2026, 1, 15))
        f.refresh_from_db()
        return f

    # ── 1. Sous le seuil : chemin synchrone inchangé ─────────────────────────
    @override_settings(VENTES_EXPORT_ASYNC_ROW_THRESHOLD=1000)
    def test_small_export_stays_synchronous(self):
        self._facture('FAC-SCA41-SMALL-1')
        with mock.patch.object(
                tasks_mod.task_build_async_export, 'apply_async') as m:
            r = self.api.get(JOURNAL_URL, {'month': '2026-01'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], XLSX_CT)
        self.assertIn('attachment', r['Content-Disposition'])
        # Un vrai classeur xlsx commence par la signature ZIP « PK ».
        self.assertEqual(r.content[:2], b'PK')
        m.assert_not_called()

    # ── 2. Au-delà du seuil : 202 + tâche Celery ─────────────────────────────
    @override_settings(VENTES_EXPORT_ASYNC_ROW_THRESHOLD=1)
    def test_large_export_goes_async(self):
        self._facture('FAC-SCA41-BIG-1')
        self._facture('FAC-SCA41-BIG-2')
        with mock.patch.object(
                tasks_mod.task_build_async_export, 'apply_async') as m:
            r = self.api.get(JOURNAL_URL, {'month': '2026-01'})
        self.assertEqual(r.status_code, 202)
        self.assertIn('job_id', r.data)
        self.assertEqual(r.data['status'], 'pending')
        self.assertIn('/export/status/', r.data['status_url'])
        m.assert_called_once()
        # Dispatch sur la queue interactive avec la bonne signature.
        _, kwargs = m.call_args
        self.assertEqual(kwargs.get('queue'), 'interactive')
        self.assertEqual(kwargs['args'][0], self.co.id)      # company_id
        self.assertEqual(kwargs['args'][1], 'journal')       # layout

    # ── 3. La tâche construit + upload sous une clé préfixée société ─────────
    @override_settings(VENTES_EXPORT_ASYNC_ROW_THRESHOLD=1)
    def test_task_uploads_company_scoped_key(self):
        self._facture('FAC-SCA41-KEY-1')
        fake = _FakeMinio()
        with mock.patch(
                'apps.ventes.utils.minio_client.get_minio_client',
                return_value=fake):
            key = tasks_mod.task_build_async_export.run(
                self.co.id, 'journal', '2026-01-01', '2026-02-01', 'tok123')
        self.assertEqual(len(fake.puts), 1)
        put = fake.puts[0]
        # Clé préfixée société (ERR75) — jamais de collision inter-tenant.
        self.assertEqual(key, put['Key'])
        self.assertTrue(put['Key'].startswith(f'exports/{self.co.id}/'))
        self.assertEqual(put['ContentType'], XLSX_CT)
        # Le corps est un vrai xlsx (signature ZIP).
        self.assertEqual(bytes(put['Body'])[:2], b'PK')

    # ── 4. Endpoint de statut borné société ──────────────────────────────────
    @override_settings(VENTES_EXPORT_ASYNC_ROW_THRESHOLD=1)
    def test_status_endpoint_company_scoped_and_ready(self):
        self._facture('FAC-SCA41-STAT-1')
        fake = _FakeMinio()
        # Déclenche l'export async pour créer le job en cache…
        with mock.patch.object(
                tasks_mod.task_build_async_export, 'apply_async'):
            r = self.api.get(JOURNAL_URL, {'month': '2026-01'})
        token = r.data['job_id']
        # …puis exécute la tâche (upload mocké) → job « ready ».
        with mock.patch(
                'apps.ventes.utils.minio_client.get_minio_client',
                return_value=fake):
            tasks_mod.task_build_async_export.run(
                self.co.id, 'journal', '2026-01-01', '2026-02-01', token)
            status_url = f'/api/django/ventes/export/status/{token}/'
            r2 = self.api.get(status_url)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['status'], 'ready')
        self.assertIn('download_url', r2.data)

    @override_settings(VENTES_EXPORT_ASYNC_ROW_THRESHOLD=1)
    def test_status_other_company_gets_404(self):
        self._facture('FAC-SCA41-SCOPE-1')
        with mock.patch.object(
                tasks_mod.task_build_async_export, 'apply_async'):
            r = self.api.get(JOURNAL_URL, {'month': '2026-01'})
        token = r.data['job_id']
        # Une AUTRE société ne doit jamais voir ce job (404 indistinct).
        other_co = Company.objects.create(slug='sca41-other', nom='Other')
        other_user = User.objects.create_user(
            username='sca41_other', password='x',
            role_legacy='responsable', company=other_co)
        other_api = _auth(other_user)
        r2 = other_api.get(f'/api/django/ventes/export/status/{token}/')
        self.assertEqual(r2.status_code, 404)

    def test_status_unknown_token_404(self):
        r = self.api.get('/api/django/ventes/export/status/does-not-exist/')
        self.assertEqual(r.status_code, 404)

    # ── Seuil : par défaut 2000, surchargeable ───────────────────────────────
    def test_default_threshold_is_2000(self):
        self.assertEqual(exports_mod.export_async_row_threshold(), 2000)

    @override_settings(VENTES_EXPORT_ASYNC_ROW_THRESHOLD=42)
    def test_threshold_overridable(self):
        self.assertEqual(exports_mod.export_async_row_threshold(), 42)
