"""APRF36 — la liste des documents coûte le même nombre de requêtes à 5 et 33
documents (versions, tags, utilisateurs annotés / préchargés), valeurs égales.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged.models import (
    Cabinet, Document, DocumentTag, DocumentTagAssignment, DocumentVersion,
    FavoriGed, Folder,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/documents/'


class ListeDocumentsRequetesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aprf36', defaults={'nom': 'APRF36'})[0]
        self.u = User.objects.create_user(
            username='aprf36-u', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        self.tag = DocumentTag.objects.create(
            company=self.co, nom='Contrats', slug='contrats')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.u)}')
        self.n = 0

    def _docs(self, count):
        for _ in range(count):
            self.n += 1
            d = Document.objects.create(
                company=self.co, folder=self.folder, nom=f'D{self.n}',
                created_by=self.u, proprietaire=self.u, locked_by=self.u)
            for v in range(1, 1 + (self.n % 3) + 1):
                DocumentVersion.objects.create(
                    company=self.co, document=d, version=v,
                    file_key=f'k{self.n}-{v}', mime=f'application/v{v}')
            DocumentTagAssignment.objects.create(
                company=self.co, document=d, tag=self.tag)
            FavoriGed.objects.create(
                company=self.co, utilisateur=self.u, document=d)

    def _liste(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(f'{BASE}?folder={self.folder.pk}')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        return len(ctx), data

    def test_requetes_constantes_et_valeurs(self):
        self._docs(5)
        q5, _data5 = self._liste()
        self._docs(28)
        q33, data33 = self._liste()
        self.assertEqual(len(data33), 33)
        self.assertEqual(q5, q33)
        for row in data33:
            doc = Document.objects.get(pk=row['id'])
            versions = list(doc.versions.order_by('-version'))
            self.assertEqual(row['version_count'], len(versions))
            self.assertEqual(row['derniere_version'], versions[0].version)
            self.assertEqual(row['derniere_mime'], versions[0].mime)
            self.assertEqual(
                [t['slug'] for t in row['tags']], ['contrats'])
            self.assertIs(row['favori'], True)
            self.assertEqual(row['locked_by_nom'], 'aprf36-u')
            self.assertEqual(row['proprietaire_nom'], 'aprf36-u')
