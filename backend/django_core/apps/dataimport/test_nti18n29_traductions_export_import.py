"""NTI18N29 — Export/import CSV du catalogue de traductions.

Couvre :
  * l'export ne rend que les clés qui portent DÉJÀ une surcharge, colonnes
    ``cle|fr|en|ar|statut_traduction`` (``complet`` seulement quand les 3
    locales sont renseignées) ;
  * le réimport upsert les colonnes de locale FOURNIES et non vides
    seulement — une colonne absente/vide ne touche JAMAIS une valeur déjà
    saisie (jamais un effacement silencieux) ;
  * le job est journalisé (``dataimport.ImportJob``, ``target='traductions'``) ;
  * isolation société ; les endpoints (réservés Responsable/Admin).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.dataimport.models import ImportJob
from apps.dataimport.translations_i18n import (
    exporter_traductions_csv, importer_traductions_csv, lignes_export,
)
from apps.parametres.models_translations import TranslationOverride
from authentication.models import Company

User = get_user_model()


class ExportTraductionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTI18N29 SA', slug='nti18n29-sa')
        cls.autre = Company.objects.create(
            nom='NTI18N29 Autre', slug='nti18n29-autre')

    def _override(self, locale, key, value, company=None):
        return TranslationOverride.objects.create(
            company=company or self.company, locale=locale, key=key,
            value=value)

    def test_ligne_complete_vs_incomplete(self):
        self._override('fr', 'nav.stock', 'Stock')
        self._override('en', 'nav.stock', 'Inventory')
        self._override('ar', 'nav.stock', 'مخزون')
        self._override('fr', 'nav.crm', 'CRM')  # en/ar manquants.

        lignes = {ligne['cle']: ligne for ligne in lignes_export(self.company)}
        self.assertEqual(lignes['nav.stock']['statut_traduction'], 'complet')
        self.assertEqual(lignes['nav.crm']['statut_traduction'], 'incomplet')
        self.assertEqual(lignes['nav.crm']['en'], '')

    def test_sans_surcharge_export_vide(self):
        self.assertEqual(lignes_export(self.company), [])
        contenu = exporter_traductions_csv(self.company).decode('utf-8')
        self.assertIn('cle,fr,en,ar,statut_traduction', contenu)

    def test_isolation_societe(self):
        self._override('fr', 'fuite', 'x', company=self.autre)
        self.assertEqual(lignes_export(self.company), [])


class ImportTraductionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTI18N29 IMP SA', slug='nti18n29-imp-sa')

    def _csv(self, texte):
        return texte.encode('utf-8')

    def test_upsert_cree_les_valeurs_fournies(self):
        job = importer_traductions_csv(
            self._csv('cle,fr,en,ar\nnav.stock,Stock,Inventory,مخزون\n'),
            'traductions.csv', self.company)
        self.assertEqual(job.statut, ImportJob.Statut.OK)
        self.assertEqual(job.created_count, 3)
        self.assertEqual(
            TranslationOverride.objects.get(
                company=self.company, locale='fr', key='nav.stock').value,
            'Stock')

    def test_colonne_absente_ne_touche_pas_la_valeur_existante(self):
        TranslationOverride.objects.create(
            company=self.company, locale='ar', key='nav.stock', value='قديم')
        importer_traductions_csv(
            self._csv('cle,fr,en\nnav.stock,Stock,Inventory\n'),
            'traductions.csv', self.company)
        # Colonne « ar » absente du CSV : la valeur AR existante survit.
        self.assertEqual(
            TranslationOverride.objects.get(
                company=self.company, locale='ar', key='nav.stock').value,
            'قديم')

    def test_valeur_vide_ne_touche_pas_la_valeur_existante(self):
        TranslationOverride.objects.create(
            company=self.company, locale='en', key='nav.crm', value='CRM')
        importer_traductions_csv(
            self._csv('cle,fr,en\nnav.crm,Relation client,\n'),
            'traductions.csv', self.company)
        self.assertEqual(
            TranslationOverride.objects.get(
                company=self.company, locale='en', key='nav.crm').value,
            'CRM')

    def test_ligne_sans_cle_journalisee_en_erreur(self):
        job = importer_traductions_csv(
            self._csv('cle,fr\n,Vide\n'), 'traductions.csv', self.company)
        self.assertEqual(job.error_count, 1)

    def test_job_journalise(self):
        importer_traductions_csv(
            self._csv('cle,fr\nnav.stock,Stock\n'),
            'traductions.csv', self.company)
        job = ImportJob.objects.get(company=self.company,
                                    target='traductions')
        self.assertEqual(job.fichier_nom, 'traductions.csv')

    def test_idempotent_rejouer_deux_fois(self):
        contenu = self._csv('cle,fr\nnav.stock,Stock\n')
        importer_traductions_csv(contenu, 'traductions.csv', self.company)
        importer_traductions_csv(contenu, 'traductions.csv', self.company)
        self.assertEqual(
            TranslationOverride.objects.filter(
                company=self.company, locale='fr', key='nav.stock').count(),
            1)


class TraductionsEndpointTests(TestCase):
    EXPORT_URL = '/api/django/imports/traductions/export.csv'
    IMPORT_URL = '/api/django/imports/traductions/import/'

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTI18N29 EP SA', slug='nti18n29-ep-sa')
        cls.admin = User.objects.create_user(
            username='nti18n29_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.normal = User.objects.create_user(
            username='nti18n29_normal', password='x', company=cls.company,
            role_legacy=User.ROLE_NORMAL)

    def _client_for(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def test_export_endpoint(self):
        TranslationOverride.objects.create(
            company=self.company, locale='fr', key='nav.stock', value='Stock')
        resp = self._client_for(self.admin).get(self.EXPORT_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nav.stock', resp.content.decode('utf-8'))

    def test_export_endpoint_refuse_role_normal(self):
        resp = self._client_for(self.normal).get(self.EXPORT_URL)
        self.assertEqual(resp.status_code, 403)

    def test_import_endpoint(self):
        fichier = SimpleUploadedFile(
            'traductions.csv', b'cle,fr\nnav.stock,Stock\n',
            content_type='text/csv')
        resp = self._client_for(self.admin).post(
            self.IMPORT_URL, {'file': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['created_count'], 1)
        self.assertTrue(
            TranslationOverride.objects.filter(
                company=self.company, locale='fr', key='nav.stock').exists())

    def test_import_endpoint_refuse_role_normal(self):
        fichier = SimpleUploadedFile(
            'traductions.csv', b'cle,fr\nnav.stock,Stock\n',
            content_type='text/csv')
        resp = self._client_for(self.normal).post(
            self.IMPORT_URL, {'file': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 403)
