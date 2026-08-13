"""NTEXT11 — export CSV/XLSX d'une définition de rapport (report-builder).

``GET reporting/rapport-definitions/<id>/export/?format=csv|xlsx`` rejoue la
définition (NTEXT10) et streame le fichier, en réutilisant les aplatissements
et le constructeur xlsx déjà en place pour les abonnements (NTEXT12).
Aucune colonne de prix d'achat / marge ne sort jamais d'un export.
"""
import csv
import io
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import data_explorer

from .models import RapportDefinition, WebVitalMetric
from .rapport_builder import _sans_colonnes_interdites

User = get_user_model()

URL = '/api/django/reporting/rapport-definitions/'

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT11 Co {next(_seq)}')


def make_user(company, username=None):
    return User.objects.create_user(
        username=username or f'ntext11-u{next(_seq)}', password='x',
        role_legacy='responsable', company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _vitals_provider(company, user):
    return WebVitalMetric.objects.filter(company=company)


def _lignes_csv(response):
    contenu = response.content.decode('utf-8-sig')
    return list(csv.reader(io.StringIO(contenu)))


class RapportExportTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT11 Export')
        self.other = make_company('NTEXT11 Autre')
        self.user = make_user(self.company, 'ntext11-owner')
        self.api = _auth(self.user)
        data_explorer.register_dataset(
            'vitals_ntext11', 'Vitals (test NTEXT11)',
            ['id', 'route', 'metric', 'value'], _vitals_provider)
        for route, metric, value in (
                ('/devis', 'LCP', 10), ('/devis', 'LCP', 5),
                ('/devis', 'INP', 2), ('/leads', 'LCP', 7)):
            WebVitalMetric.objects.create(
                company=self.company, route=route, metric=metric, value=value)
        WebVitalMetric.objects.create(
            company=self.other, route='/devis', metric='LCP', value=999)

    def _definition(self, **kwargs):
        kwargs.setdefault('titre', 'Valeur par route')
        kwargs.setdefault('dataset', 'vitals_ntext11')
        kwargs.setdefault('spec', {
            'group_by': ['route', 'metric'],
            'aggregates': [{'alias': 'total', 'fn': 'sum', 'field': 'value'}],
        })
        return RapportDefinition.objects.create(
            company=self.company, owner=self.user, **kwargs)

    def test_csv_export_of_flat_report_has_readable_headers(self):
        obj = self._definition()
        res = self.api.get(f'{URL}{obj.id}/export/?format=csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res['Content-Type'])
        self.assertIn('attachment;', res['Content-Disposition'])
        lignes = _lignes_csv(res)
        self.assertEqual(set(lignes[0]), {'route', 'metric', 'total'})
        self.assertEqual(len(lignes), 4)
        valeurs = {c for ligne in lignes[1:] for c in ligne}
        self.assertNotIn('999.0', valeurs)
        self.assertNotIn('999', valeurs)

    def test_csv_export_of_pivot_has_row_and_column_totals(self):
        obj = self._definition(pivot_spec={
            'rows': ['route'], 'columns': ['metric'],
            'measure': 'total', 'agg': 'sum',
        })
        res = self.api.get(f'{URL}{obj.id}/export/?format=csv')
        self.assertEqual(res.status_code, 200)
        lignes = _lignes_csv(res)
        self.assertEqual(lignes[0][0], 'Ligne')
        self.assertEqual(lignes[0][-1], 'Total')
        par_ligne = {ligne[0]: ligne for ligne in lignes[1:]}
        self.assertEqual(float(par_ligne['/devis'][-1]), 17)
        self.assertEqual(float(par_ligne['/leads'][-1]), 7)

    def test_xlsx_export_streams_a_workbook(self):
        obj = self._definition()
        res = self.api.get(f'{URL}{obj.id}/export/?format=xlsx')
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res['Content-Type'])
        self.assertTrue(res.content[:2] == b'PK')  # un .xlsx est un ZIP

    def test_unknown_format_is_refused(self):
        obj = self._definition()
        res = self.api.get(f'{URL}{obj.id}/export/?format=pdf')
        self.assertEqual(res.status_code, 400)

    def test_other_company_report_is_not_exportable(self):
        etranger = RapportDefinition.objects.create(
            company=self.other, titre='Étranger', dataset='vitals_ntext11',
            spec={}, partage=RapportDefinition.Partage.SOCIETE)
        res = self.api.get(f'{URL}{etranger.id}/export/?format=csv')
        self.assertEqual(res.status_code, 404)

    def test_purchase_price_columns_are_stripped(self):
        entetes = ['produit', 'prix_achat', 'Marge', 'total']
        lignes = [['Panneau', 100, 40, 140]]
        propres, lignes_propres = _sans_colonnes_interdites(entetes, lignes)
        self.assertEqual(propres, ['produit', 'total'])
        self.assertEqual(lignes_propres, [['Panneau', 140]])
