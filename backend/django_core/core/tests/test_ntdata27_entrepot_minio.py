"""Tests NTDATA27 — extraits d'entrepôt vers le MinIO interne (sans credential).

Couvre :
  * la destination ``minio`` est enregistrée et proposée par le modèle ;
  * la clé objet respecte ``<company>/<dataset>/<date>.<ext>`` ;
  * un extrait exécuté DÉPOSE un objet daté dans le bucket entrepôt ;
  * endpoint MinIO absent → no-op propre (aucun appel réseau, statut explicite) ;
  * une panne de dépôt est journalisée en statut « erreur », jamais une
    exception qui casserait le runner.
"""
from unittest import mock

from django.test import TestCase, override_settings

from authentication.models import Company
from core import data_explorer, scheduled_export
from core.integrations import get_provider_class
from core.models import ScheduledExport


def _companies_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class _FakeClient:
    """Client S3 minimal : mémorise les objets déposés (aucun réseau)."""

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


class EntrepotMinioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def setUp(self):
        data_explorer.register_dataset(
            'societes', 'Sociétés', ['id', 'nom'], _companies_dataset)

    def _export(self, **kw):
        params = dict(company=self.company, titre='Entrepôt',
                      dataset='societes', spec={'select': ['nom']},
                      format='csv', destination='minio')
        params.update(kw)
        return ScheduledExport.objects.create(**params)

    def test_destination_minio_enregistree(self):
        cls = get_provider_class(scheduled_export.TYPE_EXPORT_DEST, 'minio')
        self.assertIsNotNone(cls)
        self.assertIn('minio', dict(ScheduledExport.DEST_CHOICES))

    def test_destination_par_defaut_est_lentrepot_interne(self):
        exp = ScheduledExport.objects.create(
            company=self.company, titre='Défaut', dataset='societes')
        self.assertEqual(exp.destination, ScheduledExport.DEST_MINIO)

    def test_cle_objet_datee_par_societe_et_dataset(self):
        key = scheduled_export.warehouse_key(
            {'company_id': 7, 'dataset': 'ventes_devis', 'date': '2026-03-01'},
            'extrait.parquet')
        self.assertEqual(key, '7/ventes_devis/2026-03-01.parquet')

    @override_settings(MINIO_ENDPOINT='minio:9000')
    def test_executer_depose_un_fichier_date_dans_le_bucket(self):
        exp = self._export()
        fake = _FakeClient()
        with mock.patch.object(scheduled_export, '_minio_client',
                               return_value=fake):
            scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'ok')
        # NTDATA31 a ajouté un SECOND dépôt à côté de l'extrait : son manifeste
        # de schéma. Ce test-ci ne juge que le fichier de DONNÉES ; le manifeste
        # a le sien (``test_ntdata31_manifeste``), et on le sélectionne par son
        # suffixe plutôt que par l'ordre d'insertion du dict.
        self.assertEqual(len(fake.objects), 2)
        (bucket, key), body = next(
            (bk, v) for bk, v in fake.objects.items()
            if not bk[1].endswith('.manifest.json'))
        self.assertEqual(bucket, scheduled_export.warehouse_bucket())
        self.assertTrue(key.startswith(f'{self.company.pk}/societes/'))
        self.assertTrue(key.endswith('.csv'))
        self.assertIn(b'ACME', body)
        self.assertEqual(exp.dernier_detail.get('key'), key)

    @override_settings(MINIO_ENDPOINT='')
    def test_sans_endpoint_aucun_appel_reseau(self):
        exp = self._export()
        with mock.patch.object(scheduled_export, '_minio_client') as client:
            scheduled_export.executer(exp)
            client.assert_not_called()
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'non_configure')

    @override_settings(MINIO_ENDPOINT='minio:9000')
    def test_panne_de_depot_donne_un_statut_erreur_sans_exception(self):
        exp = self._export()
        with mock.patch.object(scheduled_export, '_minio_client',
                               side_effect=RuntimeError('minio HS')):
            scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'erreur')
        self.assertIn('échec', exp.dernier_detail.get('detail', ''))
