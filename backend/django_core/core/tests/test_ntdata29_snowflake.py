"""Tests NTDATA29 — connecteur Snowflake livré DÉSARMÉ (gated fondateur).

Couvre :
  * la destination est enregistrée et proposée par le modèle ;
  * sans variables ``SNOWFLAKE_*`` : ``is_configured()`` faux, aucun appel
    réseau, aucun import du connecteur, statut « non_configure » propre ;
  * une variable manquante suffit à garder le connecteur désarmé ;
  * le nom de table est bien DATÉ et sûr en SQL ;
  * la dépendance ``snowflake-connector-python`` reste OPTIONNELLE (absente des
    requirements : aucune dépendance payante n'entre dans le projet).
"""
import os
import re
from pathlib import Path
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from core import data_explorer, scheduled_export
from core.integrations import get_provider_class
from core.models import ScheduledExport


def _companies_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class SnowflakeDesarmeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def setUp(self):
        data_explorer.register_dataset(
            'societes', 'Sociétés', ['id', 'nom'], _companies_dataset)

    def test_destination_enregistree_et_au_catalogue(self):
        self.assertIsNotNone(
            get_provider_class(scheduled_export.TYPE_EXPORT_DEST, 'snowflake'))
        self.assertIn('snowflake', dict(ScheduledExport.DEST_CHOICES))

    def test_sans_env_non_configure_et_aucun_appel(self):
        dest = scheduled_export.SnowflakeDestination()
        with mock.patch.dict(os.environ, {k: '' for k in
                                          scheduled_export.SNOWFLAKE_ENV_REQUIRED}):
            self.assertFalse(dest.is_configured())
            with mock.patch.object(scheduled_export,
                                   '_snowflake_connect') as connect:
                res = dest.deliver('x.csv', b'a,b', 'text/csv')
                connect.assert_not_called()
        self.assertFalse(res['ok'])
        self.assertIn('non configuré', res['detail'])

    def test_une_variable_manquante_garde_le_connecteur_desarme(self):
        env = {k: 'valeur' for k in scheduled_export.SNOWFLAKE_ENV_REQUIRED}
        env['SNOWFLAKE_SCHEMA'] = ''
        dest = scheduled_export.SnowflakeDestination()
        with mock.patch.dict(os.environ, env):
            self.assertFalse(dest.is_configured())

    def test_runner_no_op_propre_sur_un_extrait_snowflake(self):
        exp = ScheduledExport.objects.create(
            company=self.company, titre='SF', dataset='societes',
            spec={'select': ['nom']}, destination='snowflake')
        with mock.patch.dict(os.environ, {k: '' for k in
                                          scheduled_export.SNOWFLAKE_ENV_REQUIRED}):
            scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'non_configure')

    def test_nom_de_table_date_et_sur(self):
        table = scheduled_export.snowflake_table(
            {'dataset': 'ventes-devis', 'date': '2026-03-01'})
        self.assertEqual(table, 'VENTES_DEVIS_20260301')
        self.assertTrue(re.fullmatch(r'[A-Z0-9_]+', table))

    def test_dependance_snowflake_reste_optionnelle(self):
        root = Path(__file__).resolve().parents[2]
        for name in ('requirements.txt', 'requirements-dev.txt'):
            content = (root / name).read_text(encoding='utf-8').lower()
            self.assertNotIn('snowflake', content)
