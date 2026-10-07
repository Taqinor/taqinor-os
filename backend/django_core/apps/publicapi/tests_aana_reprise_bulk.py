"""AANA35 — reprise des jobs bulk sans perte.

Constat C-AANA-028 :
* import JSONL ``A,<vide>,B,C,D`` interrompu après B : le curseur valait le
  NUMÉRO DE LIGNE du fichier (3), la reprise lisait ``rows[3:]`` = D — C
  n'était jamais importé et le job finissait « terminé » ;
* export repris à ``cursor=2`` : le fichier stocké ne contenait que les
  lignes d'après le curseur (2 sur 4), job « terminé ».

Vraie base, vrai ``run_import_job``/``run_export_job``, vrai service CRM ;
seul le client MinIO (frontière externe) est remplacé par un magasin en
mémoire. L'interruption de l'import est une vraie interruption du processus
(une ``BaseException`` levée pendant la ligne C, que le job ne rattrape pas),
pas un curseur posé à la main.

Run :
    python manage.py test apps.publicapi.tests_aana_reprise_bulk -v2
"""
import csv
import io
from unittest import mock

from django.test import TestCase

from apps.crm.models import Lead
from authentication.models import Company

from . import bulk
from .models import ApiKey, BulkJob
from .portees import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS


class _ProcessusTue(BaseException):
    """Le worker tué au milieu d'une ligne (jamais rattrapé par le job)."""


class RepriseBulkTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana35-co', defaults={'nom': 'AANA35'})
        self.cle, _brute = ApiKey.issue(
            company=self.co, label='bulk',
            scopes=[SCOPE_READ_LEADS, SCOPE_WRITE_LEADS])
        self.magasin = {}
        from apps.records import storage

        def deposer(fichier, _bucket, cle, ExtraArgs=None):
            self.magasin[cle] = fichier.read()

        def lire(Bucket, Key):
            return {'Body': io.BytesIO(self.magasin[Key])}

        client = mock.Mock()
        client.upload_fileobj.side_effect = deposer
        client.get_object.side_effect = lire
        for patcher in (
                mock.patch.object(storage, 'get_minio_client',
                                  return_value=client),
                mock.patch.object(storage, 'ensure_uploads_bucket')):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _job_import(self, contenu):
        job = BulkJob.objects.create(
            company=self.co, api_key=self.cle, type=BulkJob.TYPE_IMPORT,
            entite='leads', params={'mode': 'create', 'format': 'jsonl'})
        job.params['source_file_key'] = bulk._store_import_source(
            contenu, company_id=self.co.id, job_id=job.id, ext='jsonl')
        job.save(update_fields=['params'])
        return job

    def test_import_reprise_ligne_vide(self):
        contenu = ('{"nom": "A"}\n\n{"nom": "B"}\n{"nom": "C"}\n'
                   '{"nom": "D"}\n').encode('utf-8')
        job = self._job_import(contenu)
        from apps.crm import services as crm_services
        original = crm_services.create_lead_from_public_api

        def tuer_sur_c(*, company, fields):
            if fields.get('nom') == 'C':
                raise _ProcessusTue()
            return original(company=company, fields=fields)

        with mock.patch.object(crm_services, 'create_lead_from_public_api',
                               side_effect=tuer_sur_c):
            with self.assertRaises(_ProcessusTue):
                bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(sorted(Lead.objects.filter(
            company=self.co).values_list('nom', flat=True)), ['A', 'B'])
        # Le curseur compte les lignes de DONNÉES traitées (A, B), pas le
        # numéro de ligne du fichier (3, à cause de la ligne vide).
        self.assertEqual(job.cursor, 2)

        job.statut = BulkJob.STATUT_ECHEC
        job.save(update_fields=['statut'])
        bulk.run_import_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(sorted(Lead.objects.filter(
            company=self.co).values_list('nom', flat=True)),
            ['A', 'B', 'C', 'D'])
        self.assertEqual(job.succes, 4)
        self.assertEqual(job.cursor, 4)

    def test_export_reprise_complet(self):
        for nom in ('E1', 'E2', 'E3', 'E4'):
            Lead.objects.create(company=self.co, nom=nom)
        job = BulkJob.objects.create(
            company=self.co, api_key=self.cle, type=BulkJob.TYPE_EXPORT,
            entite='leads', params={'format': 'csv'}, cursor=2, succes=2,
            traites=2, statut=BulkJob.STATUT_ECHEC)

        bulk.run_export_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        lignes = list(csv.DictReader(io.StringIO(
            self.magasin[job.resultat_file_key].decode('utf-8'))))
        self.assertEqual(len(lignes), 4)
        self.assertEqual(sorted(ligne['nom'] for ligne in lignes),
                         ['E1', 'E2', 'E3', 'E4'])
        self.assertEqual(job.succes, 4)
