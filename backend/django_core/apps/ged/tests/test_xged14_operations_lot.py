"""XGED14 — Opérations par lot (multi-sélection).

Couvre :
  * 10 documents sélectionnés se taguent en une action ;
  * les items bloqués (archivé/hold) sont rapportés sans faire échouer le
    reste (jamais tout-ou-rien silencieux) ;
  * téléchargement ZIP.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import ArchivageLegalError, Cabinet, Document, DocumentTag, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XGed14Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged14-a', 'Xged14 A')
        self.admin_a = make_user(self.co_a, 'xged14-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.docs = [
            Document.objects.create(
                company=self.co_a, folder=self.folder_a, nom=f'Doc {i}')
            for i in range(10)
        ]
        self.tag = DocumentTag.objects.create(
            company=self.co_a, nom='Compta', slug='compta')


class OperationLotServiceTests(XGed14Base):
    def test_tag_10_documents(self):
        resultats, erreurs = services.operation_lot(
            self.docs, operation='tagger', params={'tag': self.tag.pk},
            user=self.admin_a)
        self.assertEqual(len(resultats), 10)
        self.assertEqual(erreurs, [])
        for doc in self.docs:
            self.assertTrue(doc.tag_assignments.filter(tag=self.tag).exists())

    def test_blocked_item_reported_without_failing_rest(self):
        blocked_doc = self.docs[0]
        with mock.patch(
                'apps.ged.services.mettre_en_corbeille',
                side_effect=lambda d, u: (
                    (_ for _ in ()).throw(ArchivageLegalError('archivé'))
                    if d.pk == blocked_doc.pk else None)):
            resultats, erreurs = services.operation_lot(
                self.docs, operation='corbeille', params={}, user=self.admin_a)
        self.assertEqual(len(erreurs), 1)
        self.assertEqual(erreurs[0]['document'], blocked_doc.pk)
        self.assertEqual(len(resultats), 9)

    def test_unknown_operation_reported_as_erreur(self):
        resultats, erreurs = services.operation_lot(
            self.docs[:1], operation='inconnue', params={}, user=self.admin_a)
        self.assertEqual(resultats, [])
        self.assertEqual(len(erreurs), 1)

    def test_zipper_documents(self):
        for doc in self.docs[:2]:
            services.add_version(
                doc, file_key='', company=self.co_a, filename=f'{doc.nom}.pdf',
                size=0, mime='application/pdf')
        with mock.patch(
                'apps.records.storage.fetch_attachment',
                return_value=(b'%PDF-1.4', None)):
            zip_bytes, erreurs = services.zipper_documents(self.docs[:3])
        self.assertGreater(len(zip_bytes), 0)
        # Le 3e document n'a aucune version → rapporté en erreur.
        self.assertEqual(len(erreurs), 1)


class OperationLotApiTests(XGed14Base):
    def test_endpoint_tag_batch(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/operations-lot/', {
            'documents': [d.pk for d in self.docs],
            'operation': 'tagger',
            'params': {'tag': self.tag.pk},
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['resultats']), 10)
        self.assertEqual(resp.data['erreurs'], [])

    def test_endpoint_requires_documents_and_operation(self):
        api = auth(self.admin_a)
        resp = api.post(
            '/api/django/ged/documents/operations-lot/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
