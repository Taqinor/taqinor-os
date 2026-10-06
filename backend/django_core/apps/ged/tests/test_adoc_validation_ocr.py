"""ADOC9 — valider une extraction OCR : palier ged_gerer, jamais sur un
document archivé, sans écraser les clés système.

Rejoue la sonde #6 de l'audit documents (2026-10-05) : un rôle « normal »
validait (200) une extraction sur un document ARCHIVÉ légalement et
`custom_data` devenait {'x': 1, 'source_type': 'ecrase'} (écriture par
queryset.update qui contournait Document.save).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields.models import CustomFieldDef
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, Folder, ValidationOcrDocument,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/validations-ocr/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ValidationOcrTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc9', defaults={'nom': 'ADOC9'})[0]
        self.admin = User.objects.create_user(
            username='adoc9-admin', password='x', company=self.co,
            role_legacy='admin')
        self.normal = User.objects.create_user(
            username='adoc9-normal', password='x', company=self.co,
            role_legacy='normal')
        self.resp = User.objects.create_user(
            username='adoc9-resp', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        self.origine = {'source_type': 'ventes.facture', 'source_id': 7}

    def _validation(self, nom):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom=nom,
            custom_data=dict(self.origine))
        return doc, ValidationOcrDocument.objects.create(
            company=self.co, document=doc, score_confiance=0.3)

    def test_role_normal_403(self):
        doc, validation = self._validation('n.pdf')
        resp = auth(self.normal).post(
            f'{BASE}{validation.pk}/valider/',
            {'champs_corriges': {'x': 1}}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.custom_data, self.origine)
        validation.refresh_from_db()
        self.assertFalse(validation.valide)

    def test_archive_403(self):
        doc, validation = self._validation('archive.pdf')
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            services.archiver_legalement(doc, user=self.admin)
        resp = auth(self.resp).post(
            f'{BASE}{validation.pk}/valider/',
            {'champs_corriges': {'x': 1}}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn('archivé', str(resp.data['detail']))
        doc.refresh_from_db()
        self.assertEqual(doc.custom_data, self.origine)

    def test_cles_systeme_preservees(self):
        CustomFieldDef.objects.create(
            company=self.co, module='document', code='montant',
            libelle='Montant', type='number')
        doc, validation = self._validation('ordinaire.pdf')
        resp = auth(self.resp).post(
            f'{BASE}{validation.pk}/valider/',
            {'champs_corriges': {'source_type': 'ecrase', 'montant': '12'}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.custom_data['source_type'], 'ventes.facture')
        self.assertEqual(doc.custom_data['source_id'], 7)
        self.assertEqual(doc.custom_data['montant'], 12.0)
