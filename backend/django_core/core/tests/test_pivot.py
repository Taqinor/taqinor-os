"""Tests FG380 — constructeur de tableau croisé (pivot/crosstab).

Couvre :
  * validation de PivotSpec (axe requis, agg connu, mesure requise sauf count) ;
  * sum croisé lignes × colonnes + totaux + grand total ;
  * count sans mesure ;
  * avg/min/max ;
  * données partielles tolérées ;
  * transformation PURE : aucun import d'app domaine, pas de DB.
"""
from django.test import SimpleTestCase

from core.pivot import PivotSpec, build_pivot


_ROWS = [
    {'ville': 'Casa', 'produit': 'Panneau', 'montant': 100},
    {'ville': 'Casa', 'produit': 'Onduleur', 'montant': 200},
    {'ville': 'Rabat', 'produit': 'Panneau', 'montant': 50},
    {'ville': 'Rabat', 'produit': 'Panneau', 'montant': 70},
]


class SpecValidationTests(SimpleTestCase):
    def test_requires_axis(self):
        with self.assertRaises(ValueError):
            PivotSpec(rows=[], columns=[])

    def test_unknown_agg(self):
        with self.assertRaises(ValueError):
            PivotSpec(rows=['ville'], measure='montant', agg='median')

    def test_measure_required_unless_count(self):
        with self.assertRaises(ValueError):
            PivotSpec(rows=['ville'], agg='sum')
        # count sans mesure : OK.
        PivotSpec(rows=['ville'], agg='count')


class BuildTests(SimpleTestCase):
    def test_sum_crosstab(self):
        spec = PivotSpec(rows=['ville'], columns=['produit'],
                         measure='montant', agg='sum')
        res = build_pivot(_ROWS, spec)
        self.assertEqual(res['cells']['Casa']['Panneau'], 100)
        self.assertEqual(res['cells']['Rabat']['Panneau'], 120)
        self.assertEqual(res['row_totals']['Casa'], 300)
        self.assertEqual(res['row_totals']['Rabat'], 120)
        self.assertEqual(res['col_totals']['Panneau'], 220)
        self.assertEqual(res['grand_total'], 420)

    def test_count(self):
        spec = PivotSpec(rows=['ville'], agg='count')
        res = build_pivot(_ROWS, spec)
        self.assertEqual(res['row_totals']['Casa'], 2)
        self.assertEqual(res['row_totals']['Rabat'], 2)
        self.assertEqual(res['grand_total'], 4)

    def test_avg_min_max(self):
        spec = PivotSpec(rows=['produit'], measure='montant', agg='avg')
        res = build_pivot(_ROWS, spec)
        self.assertAlmostEqual(res['row_totals']['Panneau'],
                               (100 + 50 + 70) / 3)
        spec_min = PivotSpec(rows=['produit'], measure='montant', agg='min')
        self.assertEqual(build_pivot(_ROWS, spec_min)['row_totals']['Panneau'],
                         50)
        spec_max = PivotSpec(rows=['produit'], measure='montant', agg='max')
        self.assertEqual(build_pivot(_ROWS, spec_max)['row_totals']['Panneau'],
                         100)

    def test_partial_data_tolerated(self):
        spec = PivotSpec(rows=['ville'], measure='montant', agg='sum')
        res = build_pivot([{'ville': 'Casa'}, {'montant': 'x'}], spec)
        self.assertEqual(res['grand_total'], 0)
