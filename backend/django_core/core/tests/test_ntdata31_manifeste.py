"""Tests NTDATA31 — manifeste d'entrepôt (schéma exporté).

Couvre :
  * le manifeste liste les colonnes ET leurs types du dernier extrait ;
  * il porte nb_lignes, dataset, mode et le curseur high-watermark ;
  * il est déposé À CÔTÉ du fichier dans l'entrepôt (``.manifest.json``) ;
  * il reste consultable sur l'extrait même quand la destination est en no-op ;
  * ``version_metriques`` est explicitement vide tant que la couche sémantique
    n'existe pas (jamais un numéro inventé).
"""
import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from core import data_explorer, scheduled_export
from core.models import ChangelogEntry, ScheduledExport


def _changelog_dataset(company, user):
    return ChangelogEntry.objects.all()


class _FakeClient:
    def __init__(self):
        self.objects = {}
        self.created_buckets = []

    def head_bucket(self, Bucket):  # noqa: N803 — signature boto3
        if Bucket not in self.created_buckets:
            raise RuntimeError('bucket absent')

    def create_bucket(self, Bucket):  # noqa: N803 — signature boto3
        self.created_buckets.append(Bucket)

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self.objects[(Bucket, Key)] = Body


class ManifesteEntrepotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.t0 = timezone.now() - timedelta(days=2)

    def setUp(self):
        data_explorer.register_dataset(
            'changelog', 'Nouveautés', ['id', 'titre', 'publie_le', 'breaking'],
            _changelog_dataset)
        ChangelogEntry.objects.create(titre='A', publie_le=self.t0,
                                      breaking=True)

    def _export(self, **kw):
        params = dict(
            company=self.company, titre='Chg', dataset='changelog',
            spec={'select': ['id', 'titre', 'publie_le', 'breaking']},
            format='csv', destination='sftp')
        params.update(kw)
        return ScheduledExport.objects.create(**params)

    def test_colonnes_et_types_du_dernier_extrait(self):
        exp = self._export()
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        manifeste = exp.dernier_detail['manifest']
        types = {c['nom']: c['type'] for c in manifeste['colonnes']}
        self.assertEqual(types['id'], scheduled_export.TYPE_ENTIER)
        self.assertEqual(types['titre'], scheduled_export.TYPE_TEXTE)
        self.assertEqual(types['publie_le'], scheduled_export.TYPE_HORODATAGE)
        self.assertEqual(types['breaking'], scheduled_export.TYPE_BOOLEEN)
        self.assertEqual([c['nom'] for c in manifeste['colonnes']],
                         ['id', 'titre', 'publie_le', 'breaking'])

    def test_manifeste_porte_nb_lignes_dataset_et_curseur(self):
        exp = self._export(mode=ScheduledExport.MODE_INCREMENTAL,
                           champ_curseur='publie_le')
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        manifeste = exp.dernier_detail['manifest']
        self.assertEqual(manifeste['dataset'], 'changelog')
        self.assertEqual(manifeste['nb_lignes'], 1)
        self.assertEqual(manifeste['mode'], 'incremental')
        self.assertEqual(manifeste['champ_curseur'], 'publie_le')
        self.assertEqual(manifeste['curseur'], exp.dernier_curseur)

    def test_version_metriques_jamais_inventee(self):
        exp = self._export()
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        manifeste = exp.dernier_detail['manifest']
        self.assertIn('version_metriques', manifeste)
        self.assertIsNone(manifeste['version_metriques'])

    def test_manifeste_consultable_meme_si_destination_non_configuree(self):
        exp = self._export(destination='s3')
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'non_configure')
        self.assertTrue(exp.dernier_detail['manifest']['colonnes'])
        self.assertNotIn('manifest_key', exp.dernier_detail)

    @override_settings(MINIO_ENDPOINT='minio:9000')
    def test_manifeste_depose_a_cote_du_fichier(self):
        exp = self._export(destination='minio')
        fake = _FakeClient()
        with mock.patch.object(scheduled_export, '_minio_client',
                               return_value=fake):
            scheduled_export.executer(exp)
        exp.refresh_from_db()
        cles = sorted(key for _bucket, key in fake.objects)
        self.assertEqual(len(cles), 2)
        manifest_keys = [k for k in cles if k.endswith('.manifest.json')]
        self.assertEqual(len(manifest_keys), 1)
        self.assertEqual(exp.dernier_detail['manifest_key'], manifest_keys[0])
        # Même préfixe société/dataset/date que le fichier de données.
        prefixe = manifest_keys[0].rsplit('.manifest.json', 1)[0]
        self.assertIn(f'{prefixe}.csv', cles)
        depose = json.loads(
            fake.objects[(scheduled_export.warehouse_bucket(),
                          manifest_keys[0])].decode('utf-8'))
        self.assertEqual(depose['dataset'], 'changelog')
        self.assertTrue(depose['colonnes'])
