"""Tests XPLT11 — mesures calculées (formules) dans le pivot et l'explorateur BI.

Couvre :
  * data_explorer.run_query : formula_measures calculées par ligne (ex.
    « ca/nb_devis »), division par zéro -> valeur vide, expression illégale ->
    FormulaError (400 côté vue SavedQueryViewSet.run_adhoc) ;
  * pivot.build_pivot : mesure formule par cellule + totaux, division par zéro
    -> cellule vide, expression illégale -> FormulaError ;
  * sauvegarde/rechargement via SavedQuery (spec JSON opaque, aucune migration
    requise) ;
  * découplage : aucun import d'app domaine.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer
from core.formula import FormulaError
from core.models import SavedQuery
from core.pivot import PivotSpec, build_pivot
from core.views import SavedQueryViewSet

User = get_user_model()


# ── Pivot : mesure formule ad-hoc ────────────────────────────────────────────

_DEVIS_ROWS = [
    {'ville': 'Casa', 'ca': 1000, 'devis': 1},
    {'ville': 'Casa', 'ca': 2000, 'devis': 1},
    {'ville': 'Rabat', 'ca': 900, 'devis': 1},
]

_EXTRA = [
    {'alias': 'ca', 'field': 'ca', 'agg': 'sum'},
    {'alias': 'nb_devis', 'field': 'devis', 'agg': 'sum'},
]


class PivotFormulaMeasureTests(SimpleTestCase):
    def test_panier_moyen_par_groupe(self):
        spec = PivotSpec(rows=['ville'], formula='ca / nb_devis',
                         extra_measures=_EXTRA)
        res = build_pivot(_DEVIS_ROWS, spec)
        # Casa : ca=3000, nb_devis=2 -> 1500. Rabat : ca=900, nb_devis=1 -> 900.
        self.assertEqual(res['row_totals']['Casa'], 1500)
        self.assertEqual(res['row_totals']['Rabat'], 900)
        self.assertEqual(res['measure'], 'ca / nb_devis')
        self.assertEqual(res['agg'], 'formula')

    def test_division_by_zero_gives_empty_cell(self):
        rows = [{'ville': 'Vide', 'ca': 500, 'devis': 0}]
        spec = PivotSpec(rows=['ville'], formula='ca / nb_devis',
                         extra_measures=_EXTRA)
        res = build_pivot(rows, spec)
        self.assertIsNone(res['row_totals']['Vide'])

    def test_illegal_formula_raises(self):
        spec = PivotSpec(rows=['ville'], formula='__import__("os")',
                         extra_measures=_EXTRA)
        with self.assertRaises(FormulaError):
            build_pivot(_DEVIS_ROWS, spec)

    def test_grand_total_and_col_totals(self):
        rows = [
            {'ville': 'Casa', 'produit': 'A', 'ca': 100, 'devis': 1},
            {'ville': 'Casa', 'produit': 'B', 'ca': 300, 'devis': 1},
        ]
        spec = PivotSpec(rows=['ville'], columns=['produit'],
                         formula='ca / nb_devis', extra_measures=_EXTRA)
        res = build_pivot(rows, spec)
        self.assertEqual(res['grand_total'], 200)  # (100+300)/(1+1)
        self.assertEqual(res['col_totals']['A'], 100)
        self.assertEqual(res['col_totals']['B'], 300)


# ── data_explorer : formula_measures par ligne ──────────────────────────────

def _users_dataset_provider(company, user):
    return User.objects.filter(company=company)


class DataExplorerFormulaMeasureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='XPLT11 ACME')
        cls.u1 = User.objects.create_user(
            username='xplt11_a', password='x', company=cls.company,
            is_active=True)
        cls.u2 = User.objects.create_user(
            username='xplt11_b', password='x', company=cls.company,
            is_active=True)

    def setUp(self):
        data_explorer.register_dataset(
            'xplt11_utilisateurs', 'Utilisateurs XPLT11',
            ['id', 'username', 'is_active'], _users_dataset_provider)

    def test_formula_measure_computed_per_row(self):
        rows = data_explorer.run_query(
            'xplt11_utilisateurs', self.company, self.u1, {
                'aggregates': [
                    {'alias': 'n', 'fn': 'count', 'field': 'id'},
                    {'alias': 'actifs', 'fn': 'count', 'field': 'id'},
                ],
                'formula_measures': [
                    {'alias': 'ratio', 'expression': 'actifs / n'},
                ],
            })
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ratio'], 1.0)

    def test_formula_measure_division_by_zero_is_none(self):
        User.objects.create_user(
            username='xplt11_inactive', password='x', company=self.company,
            is_active=False)
        rows = data_explorer.run_query(
            'xplt11_utilisateurs', self.company, self.u1, {
                'group_by': ['is_active'],
                'aggregates': [
                    {'alias': 'n', 'fn': 'count', 'field': 'id'},
                ],
                'formula_measures': [
                    # nb_inactifs (constante 0) n'existe pas côté agrégat pour
                    # la ligne is_active=True -> division par une valeur
                    # littérale 0 -> cellule vide, jamais d'exception.
                    {'alias': 'ratio', 'expression': 'n / 0'},
                ],
            })
        self.assertTrue(len(rows) >= 1)
        for row in rows:
            self.assertIsNone(row['ratio'])

    def test_illegal_formula_measure_raises(self):
        with self.assertRaises(FormulaError):
            data_explorer.run_query(
                'xplt11_utilisateurs', self.company, self.u1, {
                    'aggregates': [
                        {'alias': 'n', 'fn': 'count', 'field': 'id'}],
                    'formula_measures': [
                        {'alias': 'x', 'expression': '__import__("os")'}],
                })

    def test_run_adhoc_illegal_formula_returns_400(self):
        factory = APIRequestFactory()
        req = factory.post('/saved-queries/run/', {
            'dataset': 'xplt11_utilisateurs',
            'spec': {
                'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
                'formula_measures': [
                    {'alias': 'x', 'expression': '__import__("os")'}],
            },
        }, format='json')
        force_authenticate(req, user=self.u1)
        view = SavedQueryViewSet.as_view({'post': 'run_adhoc'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_save_and_reload_formula_measure_spec(self):
        """XPLT11 — la spec formule persiste dans SavedQuery.spec (JSON opaque,
        aucune migration requise) et se ré-exécute identique au rechargement."""
        spec = {
            'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
            'formula_measures': [{'alias': 'double_n', 'expression': 'n * 2'}],
        }
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.u1, titre='Ratio actifs',
            dataset='xplt11_utilisateurs', spec=spec)
        sq.refresh_from_db()
        self.assertEqual(sq.spec, spec)

        factory = APIRequestFactory()
        req = factory.post(f'/saved-queries/{sq.id}/run/', {}, format='json')
        force_authenticate(req, user=self.u1)
        view = SavedQueryViewSet.as_view({'post': 'run'})
        resp = view(req, pk=sq.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['rows'][0]['double_n'], 4)
