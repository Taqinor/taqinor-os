"""NTOBS6 — export de réversibilité complet en un clic (toutes les données du
tenant, formats ouverts). Aucun champ interne-only (``prix_achat``) ne doit
JAMAIS apparaître dans un dataset exporté."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role

from core import export_registry, signed_download
from core.tasks import export_reversibilite_tenant

User = get_user_model()


class ExportAllDatasetsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs6')

    def test_at_least_four_datasets_registered(self):
        # crm/ventes/stock/sav/installations s'enregistrent tous dans leur
        # ready() (apps/*/bi_datasets.py) — déjà chargés au démarrage Django.
        self.assertGreaterEqual(len(export_registry.datasets_disponibles()), 4)

    def test_stock_produits_never_exposes_prix_achat(self):
        fichiers, comptes = export_registry.export_all_datasets(self.company)
        self.assertIn('stock_produits.csv', fichiers)
        header = fichiers['stock_produits.csv'].decode('utf-8').splitlines()[0]
        self.assertNotIn('prix_achat', header)
        self.assertNotIn('valeur_achat', header)
        self.assertIn('stock_produits', comptes)

    def test_at_least_four_csv_files_produced(self):
        fichiers, _comptes = export_registry.export_all_datasets(self.company)
        self.assertGreaterEqual(len(fichiers), 4)

    def test_one_dataset_failure_never_blocks_the_others(self):
        original = export_registry._export_data_explorer_dataset

        def flaky(name, company):
            if name == 'stock_produits':
                raise RuntimeError('boom')
            return original(name, company)

        with mock.patch(
                'core.export_registry._export_data_explorer_dataset',
                side_effect=flaky):
            fichiers, comptes = export_registry.export_all_datasets(self.company)
        # Le dataset en échec est absent ; les autres sont bien produits —
        # jamais une exception remontée qui viderait tout le ZIP.
        self.assertNotIn('stock_produits.csv', fichiers)
        self.assertNotIn('stock_produits', comptes)
        self.assertGreaterEqual(len(fichiers), 3)


class CustomRegistryTest(TestCase):
    def tearDown(self):
        export_registry.clear_custom_registry()

    def test_register_and_export_bespoke_dataset(self):
        def qs_fn(company):
            return list(range(3))

        def csv_fn(rows):
            return f'n\n{len(rows)}\n'.encode('utf-8')

        export_registry.register_export_dataset('mon_app', qs_fn, csv_fn)
        self.assertIn('mon_app', export_registry.datasets_disponibles())

        company = Company.objects.create(nom='Acme', slug='acme-ntobs6b')
        with mock.patch(
                'core.export_registry._data_explorer_dataset_names',
                return_value=[]):
            fichiers, comptes = export_registry.export_all_datasets(company)
        self.assertEqual(fichiers['mon_app.csv'], b'n\n3\n')
        self.assertEqual(comptes['mon_app'], 3)

    def test_invalid_registration_raises(self):
        with self.assertRaises(ValueError):
            export_registry.register_export_dataset('x', None, None)


class SignedDownloadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs6c')

    def test_resolves_active_non_expired_link(self):
        lien = signed_download.creer_lien(
            self.company, 'bucket-x', 'key-y', taille_octets=100)
        resolu = signed_download.resoudre_lien(lien.token)
        self.assertEqual(resolu, ('bucket-x', 'key-y'))

    def test_unknown_token_returns_none(self):
        self.assertIsNone(signed_download.resoudre_lien('inconnu'))

    def test_revoked_link_never_resolves(self):
        lien = signed_download.creer_lien(self.company, 'b', 'k')
        lien.actif = False
        lien.save(update_fields=['actif'])
        self.assertIsNone(signed_download.resoudre_lien(lien.token))

    def test_expired_link_never_resolves(self):
        from django.utils import timezone
        lien = signed_download.creer_lien(self.company, 'b', 'k', expiry_days=7)
        lien.expire_le = timezone.now() - timezone.timedelta(seconds=1)
        lien.save(update_fields=['expire_le'])
        self.assertIsNone(signed_download.resoudre_lien(lien.token))


class ExportReversibiliteTaskTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs6d')

    def test_task_uploads_zip_and_creates_signed_link(self):
        fake_client = mock.MagicMock()
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            result = export_reversibilite_tenant(self.company.id)
        self.assertTrue(result['ok'])
        self.assertTrue(fake_client.put_object.called)
        _args, kwargs = fake_client.put_object.call_args
        self.assertEqual(kwargs['Bucket'], 'erp-reversibilite')
        # Le ZIP a bien été uploadé et un lien signé créé.
        resolu = signed_download.resoudre_lien(result['token'])
        self.assertIsNotNone(resolu)

    def test_task_never_raises_when_company_unknown(self):
        result = export_reversibilite_tenant(999999)
        self.assertFalse(result['ok'])


class DeclencherExportEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs6e')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial')
        self.directeur = User.objects.create_user(
            'directeur6', password='x', company=self.company,
            role=self.role_directeur)
        self.commercial = User.objects.create_user(
            'commercial6', password='x', company=self.company,
            role=self.role_commercial)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_directeur_can_trigger_export(self):
        with mock.patch(
                'core.tasks.export_reversibilite_tenant.delay') as delay:
            resp = self._client(self.directeur).post(
                '/api/django/core/export-reversibilite/')
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(delay.called)

    def test_non_directeur_forbidden(self):
        resp = self._client(self.commercial).post(
            '/api/django/core/export-reversibilite/')
        self.assertEqual(resp.status_code, 403)


class TelechargerExportEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs6f')

    def test_valid_token_streams_the_zip(self):
        fake_client = mock.MagicMock()
        fake_client.get_object.return_value = {
            'Body': mock.MagicMock(read=lambda: b'PK\x03\x04fake-zip'),
        }
        lien = signed_download.creer_lien(self.company, 'bucket', 'key.zip')
        with mock.patch('core.backup._minio_client', return_value=fake_client):
            resp = APIClient().get(
                f'/api/django/core/export-reversibilite/telecharger/'
                f'{lien.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')

    def test_unknown_token_is_404(self):
        resp = APIClient().get(
            '/api/django/core/export-reversibilite/telecharger/bogus/')
        self.assertEqual(resp.status_code, 404)
