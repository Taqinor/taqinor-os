"""NTI18N45 — Export/import CSV du calendrier de jours fériés multi-pays.

Couvre :
  * l'export rend TOUTES les lignes ``Holiday`` de la société, colonnes
    ``pays|date|libelle|recurrent_annuel`` ;
  * le réimport upsert par clé ``(pays, date)`` — critère d'acceptation :
    un CSV de 30 lignes (fériés France + Sénégal) s'importe SANS DOUBLON en
    rejouant l'import deux fois ;
  * une ligne sans libellé/date, ou avec une date invalide, est journalisée
    en erreur sans faire échouer le reste de l'import ;
  * le job est journalisé (``dataimport.ImportJob``, ``target='feries'``) ;
  * isolation société ; les endpoints (réservés Responsable/Admin).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.dataimport.holidays_import import (
    exporter_feries_csv, importer_feries_csv, lignes_export,
)
from apps.dataimport.models import ImportJob
from apps.notifications.models import Holiday
from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class ExportFeriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('nti18n45-sa', 'NTI18N45 SA')
        cls.autre = make_company('nti18n45-autre', 'NTI18N45 Autre')

    def test_lignes_export_toutes_colonnes(self):
        Holiday.objects.create(
            company=self.company, pays='FR', date='2026-07-14',
            nom='Fête nationale', recurrent_annuel=True)
        lignes = lignes_export(self.company)
        self.assertEqual(lignes, [{
            'pays': 'FR', 'date': '2026-07-14',
            'libelle': 'Fête nationale', 'recurrent_annuel': 'oui',
        }])

    def test_recurrent_annuel_faux_exporte_non(self):
        Holiday.objects.create(
            company=self.company, pays='MA', date='2026-01-11',
            nom='Manifeste indépendance', recurrent_annuel=False)
        lignes = lignes_export(self.company)
        self.assertEqual(lignes[0]['recurrent_annuel'], 'non')

    def test_sans_ferie_export_vide(self):
        self.assertEqual(lignes_export(self.company), [])
        contenu = exporter_feries_csv(self.company).decode('utf-8')
        self.assertIn('pays,date,libelle,recurrent_annuel', contenu)

    def test_isolation_societe(self):
        Holiday.objects.create(
            company=self.autre, pays='SN', date='2026-04-04',
            nom='Fête indépendance')
        self.assertEqual(lignes_export(self.company), [])

    def test_tri_par_pays_puis_date(self):
        Holiday.objects.create(
            company=self.company, pays='SN', date='2026-01-01', nom='SN NY')
        Holiday.objects.create(
            company=self.company, pays='FR', date='2026-12-25', nom='Noël')
        Holiday.objects.create(
            company=self.company, pays='FR', date='2026-01-01', nom='FR NY')
        lignes = lignes_export(self.company)
        self.assertEqual(
            [(ligne['pays'], ligne['date']) for ligne in lignes],
            [('FR', '2026-01-01'), ('FR', '2026-12-25'), ('SN', '2026-01-01')])


class ImportFeriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('nti18n45-imp-sa', 'NTI18N45 IMP SA')

    def _csv(self, texte):
        return texte.encode('utf-8')

    def test_upsert_cree_les_lignes_fournies(self):
        job = importer_feries_csv(
            self._csv(
                'pays,date,libelle,recurrent_annuel\n'
                'FR,2026-07-14,Fête nationale,oui\n'
                'SN,2026-04-04,Fête indépendance,oui\n'),
            'feries.csv', self.company)
        self.assertEqual(job.statut, ImportJob.Statut.OK)
        self.assertEqual(job.created_count, 2)
        fr = Holiday.objects.get(company=self.company, pays='FR')
        self.assertEqual(str(fr.date), '2026-07-14')
        self.assertEqual(fr.nom, 'Fête nationale')
        self.assertTrue(fr.recurrent_annuel)

    def test_pays_absent_retombe_sur_ma(self):
        importer_feries_csv(
            self._csv('date,libelle\n2026-11-06,Marche verte\n'),
            'feries.csv', self.company)
        self.assertTrue(
            Holiday.objects.filter(
                company=self.company, pays='MA',
                nom='Marche verte').exists())

    def test_critere_acceptation_30_lignes_idempotent_rejoue_deux_fois(self):
        lignes = ['pays,date,libelle,recurrent_annuel']
        for jour in range(1, 16):
            lignes.append(f'FR,2026-01-{jour:02d},Jour FR {jour},non')
        for jour in range(1, 16):
            lignes.append(f'SN,2026-02-{jour:02d},Jour SN {jour},non')
        contenu = self._csv('\n'.join(lignes) + '\n')
        self.assertEqual(len(lignes) - 1, 30)  # 30 lignes de données

        job1 = importer_feries_csv(contenu, 'feries.csv', self.company)
        self.assertEqual(job1.created_count, 30)
        self.assertEqual(Holiday.objects.filter(company=self.company).count(), 30)

        job2 = importer_feries_csv(contenu, 'feries.csv', self.company)
        self.assertEqual(job2.updated_count, 30)
        self.assertEqual(job2.created_count, 0)
        # AUCUN doublon après un second passage.
        self.assertEqual(Holiday.objects.filter(company=self.company).count(), 30)

    def test_libelle_manquant_journalise_en_erreur(self):
        job = importer_feries_csv(
            self._csv('pays,date,libelle\nFR,2026-07-14,\n'),
            'feries.csv', self.company)
        self.assertEqual(job.error_count, 1)
        self.assertFalse(Holiday.objects.filter(company=self.company).exists())

    def test_date_invalide_journalisee_en_erreur_sans_bloquer_les_autres(self):
        job = importer_feries_csv(
            self._csv(
                'pays,date,libelle\n'
                'FR,14/07/2026,Fête nationale\n'
                'SN,2026-04-04,Fête indépendance\n'),
            'feries.csv', self.company)
        self.assertEqual(job.error_count, 1)
        self.assertEqual(job.created_count, 1)
        self.assertTrue(
            Holiday.objects.filter(company=self.company, pays='SN').exists())

    def test_meme_libelle_deux_pays_meme_date_journalise_le_conflit(self):
        # La contrainte (company, date, nom) est ANTÉRIEURE à ce module :
        # un très rare conflit exact est journalisé en erreur pour CETTE
        # ligne, jamais un import qui plante en entier.
        job = importer_feries_csv(
            self._csv(
                'pays,date,libelle\n'
                'FR,2026-01-01,Jour de l\'An\n'
                'SN,2026-01-01,Jour de l\'An\n'),
            'feries.csv', self.company)
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.error_count, 1)

    def test_job_journalise(self):
        importer_feries_csv(
            self._csv('pays,date,libelle\nFR,2026-07-14,Fête nationale\n'),
            'feries.csv', self.company)
        job = ImportJob.objects.get(company=self.company, target='feries')
        self.assertEqual(job.fichier_nom, 'feries.csv')


class FeriesEndpointTests(TestCase):
    EXPORT_URL = '/api/django/imports/feries/export.csv'
    IMPORT_URL = '/api/django/imports/feries/import/'

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('nti18n45-ep-sa', 'NTI18N45 EP SA')
        cls.admin = User.objects.create_user(
            username='nti18n45_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.normal = User.objects.create_user(
            username='nti18n45_normal', password='x', company=cls.company,
            role_legacy=User.ROLE_NORMAL)

    def _client_for(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def test_export_endpoint(self):
        Holiday.objects.create(
            company=self.company, pays='FR', date='2026-07-14',
            nom='Fête nationale')
        resp = self._client_for(self.admin).get(self.EXPORT_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Fête nationale', resp.content.decode('utf-8'))

    def test_export_endpoint_refuse_role_normal(self):
        resp = self._client_for(self.normal).get(self.EXPORT_URL)
        self.assertEqual(resp.status_code, 403)

    def test_import_endpoint(self):
        fichier = SimpleUploadedFile(
            'feries.csv',
            b'pays,date,libelle\nFR,2026-07-14,Fete nationale\n',
            content_type='text/csv')
        resp = self._client_for(self.admin).post(
            self.IMPORT_URL, {'file': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['created_count'], 1)
        self.assertTrue(
            Holiday.objects.filter(company=self.company, pays='FR').exists())

    def test_import_endpoint_refuse_role_normal(self):
        fichier = SimpleUploadedFile(
            'feries.csv', b'pays,date,libelle\nFR,2026-07-14,x\n',
            content_type='text/csv')
        resp = self._client_for(self.normal).post(
            self.IMPORT_URL, {'file': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 403)
