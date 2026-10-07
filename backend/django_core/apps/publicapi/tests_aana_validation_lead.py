"""AANA39 — les champs de lead écrits par l'API publique et l'import bulk
sont validés champ par champ (choix, e-mail, longueurs) → 400.

Constat C-AANA-041 : ``POST {nom:'X', canal:'nimporte',
email:'pas-un-email'}`` répondait 201 et stockait ``('nimporte',
'pas-un-email')`` — un canal hors liste casse les tableaux de bord, un
e-mail invalide casse la cadence de relance. Désormais la validation lit le
champ de modèle (``Lead._meta``) AVANT l'appel au service CRM (inchangé).

Vraie vue, vrai import bulk, vraie base ; seul le client MinIO (frontière
externe) est remplacé par un magasin en mémoire.

Run :
    python manage.py test apps.publicapi.tests_aana_validation_lead -v2
"""
import io
import json
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from authentication.models import Company

from . import bulk
from .models import ApiKey, BulkJob
from .portees import SCOPE_WRITE_LEADS

URL = '/api/public/v1/leads-write/'


class ValidationLeadTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana39-co', defaults={'nom': 'AANA39'})
        self.cle, brute = ApiKey.issue(
            company=self.co, label='ecriture', scopes=[SCOPE_WRITE_LEADS])
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f'Api-Key {brute}')

    def _canal_valide(self):
        return Lead._meta.get_field('canal').choices[0][0]

    def test_choix_et_email_valides(self):
        resp = self.api.post(URL, {
            'nom': 'X', 'canal': 'nimporte', 'email': 'pas-un-email'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        corps = json.dumps(resp.data, ensure_ascii=False, default=str)
        self.assertIn('canal', corps)
        self.assertIn('email', corps)
        self.assertFalse(Lead.objects.filter(company=self.co).exists())

    def test_longueur_depassee_400(self):
        longueur = Lead._meta.get_field('ville').max_length
        resp = self.api.post(URL, {'nom': 'Y', 'ville': 'v' * (longueur + 1)},
                             format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ville', json.dumps(resp.data, default=str))
        self.assertFalse(Lead.objects.filter(company=self.co).exists())

    def test_valeurs_valides_201(self):
        canal = self._canal_valide()
        resp = self.api.post(URL, {
            'nom': 'Z', 'canal': canal, 'email': 'z@example.com'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(company=self.co)
        self.assertEqual((lead.canal, lead.email), (canal, 'z@example.com'))

    def test_patch_valide_aussi(self):
        lead = Lead.objects.create(company=self.co, nom='Existant')
        resp = self.api.patch(f'{URL}{lead.pk}/', {'email': 'pas-un-email'},
                              format='json')
        self.assertEqual(resp.status_code, 400)
        lead.refresh_from_db()
        self.assertNotEqual(lead.email, 'pas-un-email')

    def test_import_bulk_ligne_invalide_en_erreur(self):
        magasin = {}
        from apps.records import storage

        def deposer(fichier, _bucket, cle, ExtraArgs=None):
            magasin[cle] = fichier.read()

        def lire(Bucket, Key):
            return {'Body': io.BytesIO(magasin[Key])}

        client = mock.Mock()
        client.upload_fileobj.side_effect = deposer
        client.get_object.side_effect = lire
        with mock.patch.object(storage, 'get_minio_client',
                               return_value=client), \
                mock.patch.object(storage, 'ensure_uploads_bucket'):
            job = BulkJob.objects.create(
                company=self.co, api_key=self.cle, type=BulkJob.TYPE_IMPORT,
                entite='leads', params={'mode': 'create', 'format': 'csv'})
            job.params['source_file_key'] = bulk._store_import_source(
                ('nom,email,canal\n'
                 'Bon,bon@example.com,\n'
                 'Mauvais,pas-un-email,nimporte\n').encode('utf-8'),
                company_id=self.co.id, job_id=job.id, ext='csv')
            job.save(update_fields=['params'])
            bulk.run_import_job(job.id)

        job.refresh_from_db()
        self.assertEqual((job.succes, job.erreurs), (1, 1))
        self.assertEqual(
            list(Lead.objects.filter(company=self.co).values_list(
                'nom', flat=True)), ['Bon'])
