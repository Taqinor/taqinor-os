"""NTOBS20 — sélection des jeux de données pour l'export de réversibilité.

Le paramètre ``datasets`` (liste de noms de dataset) est DÉJÀ câblé de bout en
bout : ``core.export_registry.declencher_export_reversibilite`` le lit du
corps de requête (``request.data.get('datasets')``) et le transmet à
``core.tasks.export_reversibilite_tenant``, qui filtre les fichiers du ZIP en
conséquence (voir ``core/tasks.py``). Ce module ferme le trou de couverture :
aucun test n'exerçait encore ce chemin bout en bout. La moitié frontend
(``ExportReversibilitePage.jsx`` wizard 2 étapes) est hors périmètre de cette
lane (``frontend/src`` appartient à une autre lane)."""
import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company
from core.tasks import export_reversibilite_tenant

User = get_user_model()


class ExportReversibiliteDatasetsSelectionTaskTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs20-acme')

    def _uploaded_zip_names(self, fake_client):
        _args, kwargs = fake_client.put_object.call_args
        buf = io.BytesIO(kwargs['Body'])
        with zipfile.ZipFile(buf) as zf:
            return set(zf.namelist())

    def test_only_selected_dataset_is_included(self):
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            result = export_reversibilite_tenant(
                self.company.id, datasets=['stock_produits'])
        self.assertTrue(result['ok'])
        noms = self._uploaded_zip_names(fake_client)
        self.assertEqual(noms, {'stock_produits.csv', 'manifest.json'})

    def test_no_datasets_selection_keeps_default_behaviour(self):
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            result = export_reversibilite_tenant(self.company.id)
        self.assertTrue(result['ok'])
        noms = self._uploaded_zip_names(fake_client)
        # comportement par défaut inchangé : au moins les 4 datasets connus
        # (crm/ventes/stock/sav/installations) + le manifest.
        self.assertGreaterEqual(len(noms), 5)
        self.assertIn('manifest.json', noms)

    def test_empty_datasets_list_falls_back_to_default(self):
        """``datasets=[]`` (falsy) doit se comporter comme l'absence de
        sélection — jamais un ZIP vide."""
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            result = export_reversibilite_tenant(self.company.id, datasets=[])
        self.assertTrue(result['ok'])
        noms = self._uploaded_zip_names(fake_client)
        self.assertGreaterEqual(len(noms), 5)


class DeclencherExportDatasetsForwardingTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs20-b')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.directeur = User.objects.create_user(
            'directeur20', password='x', company=self.company,
            role=self.role_directeur)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.directeur)

    def test_datasets_forwarded_from_request_body_to_task(self):
        with mock.patch(
                'core.tasks.export_reversibilite_tenant.delay') as delay:
            resp = self.client_api.post(
                '/api/django/core/export-reversibilite/',
                {'datasets': ['stock_produits']}, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(delay.called)
        _args, kwargs = delay.call_args
        self.assertEqual(kwargs.get('datasets'), ['stock_produits'])

    def test_no_datasets_key_forwards_none(self):
        with mock.patch(
                'core.tasks.export_reversibilite_tenant.delay') as delay:
            resp = self.client_api.post('/api/django/core/export-reversibilite/')
        self.assertEqual(resp.status_code, 202)
        _args, kwargs = delay.call_args
        self.assertIsNone(kwargs.get('datasets'))
