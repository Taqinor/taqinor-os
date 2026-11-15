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

    def test_limite_douce_ne_saute_aucune_ligne(self):
        """ACEL33 — la limite douce (120 s) tombe sur la ligne 4 : elle n'est
        pas comptée en erreur, le curseur reste avant elle, le journal déjà
        accumulé (ligne 2 invalide) est écrit, et la reprise l'importe."""
        import json
        from celery.exceptions import SoftTimeLimitExceeded
        lignes = [{'nom': 'L1'}, {'nom': 'L2', 'email': 'pas-un-email'},
                  {'nom': 'L3'}, {'nom': 'L4'}, {'nom': 'L5'}]
        job = self._job_import('\n'.join(
            json.dumps(x) for x in lignes).encode('utf-8'))
        original = bulk._process_lead_row

        def limite_sur_l4(company, mode, dedup_key, row):
            if row.get('nom') == 'L4':
                raise SoftTimeLimitExceeded()
            return original(company, mode, dedup_key, row)

        with mock.patch.object(bulk, '_process_lead_row',
                               side_effect=limite_sur_l4):
            bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_ECHEC)
        self.assertEqual((job.cursor, job.erreurs), (3, 1))
        journal = self.magasin[job.erreurs_file_key].decode('utf-8')
        self.assertEqual(
            [json.loads(x)['ligne'] for x in journal.splitlines()], [2])

        with mock.patch.object(bulk, '_dispatch_import'):
            bulk.relancer_job(job)
        bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(job.succes, 4)
        noms = list(Lead.objects.filter(company=self.co).order_by(
            'nom').values_list('nom', flat=True))
        self.assertEqual(noms, ['L1', 'L3', 'L4', 'L5'])
        bulk.run_import_job(job.id)  # job terminé : ne fait rien
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 4)

    def _limite_sur(self, cle_fautive):
        """Le client MinIO lève la limite douce pour UNE clé (ACEL97)."""
        from celery.exceptions import SoftTimeLimitExceeded
        from apps.records import storage
        lire = storage.get_minio_client.return_value.get_object.side_effect

        def get_object(Bucket, Key):
            if Key == cle_fautive:
                raise SoftTimeLimitExceeded()
            return lire(Bucket, Key)

        storage.get_minio_client.return_value.get_object.side_effect = (
            get_object)

    def test_limite_douce_a_la_lecture_du_stockage_solde_le_job(self):
        """ACEL97 — la limite douce levée à la lecture de la source, puis du
        journal d'erreurs, solde le job `echec` relançable (curseur et
        journal inchangés) au lieu de le laisser `en_file`."""
        import json
        lignes = [{'nom': 'L1'}, {'nom': 'L2'}, {'nom': 'L3'}]
        job = self._job_import('\n'.join(
            json.dumps(x) for x in lignes).encode('utf-8'))
        self._limite_sur(job.params['source_file_key'])
        bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_ECHEC)
        self.assertIn('Limite de temps atteinte', job.message_erreur)
        with mock.patch.object(bulk, '_dispatch_import'):
            bulk.relancer_job(job)  # accepté : le job est relançable
        self.magasin_lire_normal = None

        from apps.records import storage
        client = storage.get_minio_client.return_value
        client.get_object.side_effect = (
            lambda Bucket, Key: {'Body': io.BytesIO(self.magasin[Key])})
        bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(job.succes, 3)

        # Journal d'erreurs (ligne 2) : la limite à sa lecture ne le vide pas.
        job2 = self._job_import(b'{"nom": "M1"}\n{"nom": "M2"}\n')
        journal = bulk._store_import_source(
            b'{"ligne": 2, "erreur": "x", "donnees": {}}',
            company_id=self.co.id, job_id=f'{job2.id}-erreurs', ext='jsonl')
        job2.statut = BulkJob.STATUT_ECHEC
        job2.cursor, job2.erreurs, job2.erreurs_file_key = 1, 1, journal
        job2.save(update_fields=[
            'statut', 'cursor', 'erreurs', 'erreurs_file_key'])
        self._limite_sur(journal)
        bulk.run_import_job(job2.id)
        job2.refresh_from_db()
        self.assertEqual(job2.statut, BulkJob.STATUT_ECHEC)
        self.assertEqual((job2.cursor, job2.erreurs_file_key), (1, journal))
        self.assertIn('Limite de temps atteinte', job2.message_erreur)

    def test_limite_douce_apres_creation_ne_double_pas_le_lead(self):
        """ACEL83 — limite douce tombée APRÈS la création du lead de la
        ligne 2 : la ligne est annulée en bloc, la reprise donne un lead
        par ligne (pas de doublon)."""
        import json
        from celery.exceptions import SoftTimeLimitExceeded
        from apps.crm import leads_intake
        lignes = [{'nom': 'M1'}, {'nom': 'M2'}, {'nom': 'M3'}]
        job = self._job_import('\n'.join(
            json.dumps(x) for x in lignes).encode('utf-8'))
        original = leads_intake.finaliser_lead_importe
        appels = []

        def limite_une_fois(lead, **kwargs):
            appels.append(lead.nom)
            if len(appels) == 2:
                raise SoftTimeLimitExceeded()
            return original(lead, **kwargs)

        with mock.patch.object(leads_intake, 'finaliser_lead_importe',
                               side_effect=limite_une_fois):
            bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_ECHEC)
        self.assertEqual(job.cursor, 1)

        with mock.patch.object(bulk, '_dispatch_import'):
            bulk.relancer_job(job)
        bulk.run_import_job(job.id)
        job.refresh_from_db()
        self.assertEqual(job.statut, BulkJob.STATUT_TERMINE)
        self.assertEqual(job.cursor, 3)
        self.assertEqual(sorted(Lead.objects.filter(
            company=self.co).values_list('nom', flat=True)),
            ['M1', 'M2', 'M3'])

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
