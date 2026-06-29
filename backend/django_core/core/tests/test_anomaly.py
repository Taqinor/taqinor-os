"""Tests FG360 — détection d'anomalies (stock / paiements / fraude).

Couvre :
  * ``scan_for_outliers`` : z-score pur, seuils, écart-type nul, petit échantillon,
    valeurs non numériques ignorées, tri par amplitude ;
  * ``record_anomaly`` / ``record_outliers`` : persistance multi-tenant (société
    imposée), gravité dérivée, dédoublonnage des flags ouverts ;
  * le modèle ``AnomalyFlag`` (choix FR, scoping par société).
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from core.anomaly import (
    OutlierCandidate,
    record_anomaly,
    record_outliers,
    scan_for_outliers,
)
from core.models import AnomalyFlag


# --- scan_for_outliers (pur, sans base) --------------------------------------

class ScanForOutliersTests(SimpleTestCase):
    def test_flags_high_outlier(self):
        points = [{'id': i, 'value': 10} for i in range(10)]
        points.append({'id': 'X', 'value': 1000})
        out = scan_for_outliers(points, z_threshold=3.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].subject_id, 'X')
        self.assertEqual(out[0].direction, 'haut')
        self.assertGreater(out[0].score, 3.0)

    def test_flags_low_outlier_direction(self):
        points = [{'id': i, 'value': 100} for i in range(10)]
        points.append({'id': 'low', 'value': 1})
        out = scan_for_outliers(points, z_threshold=2.5)
        self.assertEqual(out[0].subject_id, 'low')
        self.assertEqual(out[0].direction, 'bas')
        self.assertLess(out[0].score, 0)

    def test_no_outlier_when_uniform(self):
        points = [{'id': i, 'value': 5} for i in range(20)]
        self.assertEqual(scan_for_outliers(points), [])

    def test_small_sample_never_flags(self):
        points = [{'id': 1, 'value': 1}, {'id': 2, 'value': 1000}]
        self.assertEqual(scan_for_outliers(points, min_points=4), [])

    def test_non_numeric_values_ignored(self):
        # 30 points serrés autour de 10 + une valeur non numérique (ignorée) + un
        # pic franc : le pic est signalé, la valeur non numérique jamais (elle ne
        # casse pas non plus le calcul).
        points = [{'id': i, 'value': 10 + (i % 3)} for i in range(30)]
        points.append({'id': 'bad', 'value': 'NaN-ish'})
        points.append({'id': 'big', 'value': 900})
        out = scan_for_outliers(points, z_threshold=3.0)
        ids = {c.subject_id for c in out}
        self.assertIn('big', ids)
        self.assertNotIn('bad', ids)

    def test_sorted_by_amplitude(self):
        points = [{'id': i, 'value': 10} for i in range(10)]
        points.append({'id': 'a', 'value': 200})
        points.append({'id': 'b', 'value': 2000})
        out = scan_for_outliers(points, z_threshold=1.5)
        self.assertEqual(out[0].subject_id, 'b')  # le plus aberrant d'abord

    def test_custom_keys(self):
        points = [{'pk': i, 'montant': 10, 'nom': f'p{i}'} for i in range(10)]
        points.append({'pk': 'z', 'montant': 999, 'nom': 'pic'})
        out = scan_for_outliers(points, value_key='montant', id_key='pk',
                                label_key='nom')
        self.assertEqual(out[0].subject_id, 'z')
        self.assertEqual(out[0].label, 'pic')

    def test_empty_input(self):
        self.assertEqual(scan_for_outliers([]), [])
        self.assertEqual(scan_for_outliers(None), [])


# --- record_anomaly / record_outliers (multi-tenant, base) -------------------

class RecordAnomalyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Taqinor Test')
        cls.other = Company.objects.create(nom='Autre Test')

    def test_record_forces_company_and_defaults(self):
        flag = record_anomaly(company=self.company, message='Paiement suspect',
                              category=AnomalyFlag.CATEGORY_PAIEMENT, score=4.5)
        self.assertEqual(flag.company, self.company)
        self.assertEqual(flag.status, AnomalyFlag.STATUS_OUVERT)
        # score 4.5 → avertissement (>=4, <5).
        self.assertEqual(flag.severity, AnomalyFlag.SEVERITY_AVERTISSEMENT)

    def test_severity_from_score(self):
        crit = record_anomaly(company=self.company, message='m', score=6.0,
                              metric='a')
        self.assertEqual(crit.severity, AnomalyFlag.SEVERITY_CRITIQUE)
        info = record_anomaly(company=self.company, message='m', score=3.2,
                              metric='b')
        self.assertEqual(info.severity, AnomalyFlag.SEVERITY_INFO)

    def test_dedupe_keeps_single_open_flag(self):
        a = record_anomaly(company=self.company, message='Stock négatif',
                           subject_type='stock.Produit', subject_id='42',
                           metric='quantite')
        b = record_anomaly(company=self.company, message='Stock négatif (bis)',
                           subject_type='stock.Produit', subject_id='42',
                           metric='quantite')
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(
            AnomalyFlag.objects.filter(company=self.company).count(), 1)

    def test_dedupe_is_per_company(self):
        record_anomaly(company=self.company, message='m', subject_id='1',
                       metric='q')
        record_anomaly(company=self.other, message='m', subject_id='1',
                       metric='q')
        self.assertEqual(AnomalyFlag.objects.count(), 2)

    def test_record_outliers_builds_french_messages(self):
        cands = [
            OutlierCandidate(subject_id='7', value=999.0, expected=10.0,
                             score=6.1, direction='haut', label='Produit X'),
        ]
        flags = record_outliers(cands, company=self.company,
                                category=AnomalyFlag.CATEGORY_STOCK,
                                subject_type='stock.Produit', metric='quantite')
        self.assertEqual(len(flags), 1)
        self.assertIn('Produit X', flags[0].message)
        self.assertIn('élevé', flags[0].message)
        self.assertEqual(flags[0].category, AnomalyFlag.CATEGORY_STOCK)
        self.assertEqual(flags[0].value, 999.0)

    def test_str_is_readable(self):
        flag = record_anomaly(company=self.company, message='Anomalie',
                              severity=AnomalyFlag.SEVERITY_CRITIQUE)
        self.assertIn('Anomalie', str(flag))
        self.assertIn('Critique', str(flag))
