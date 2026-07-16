"""Tests SCA48 — Plancher k-anonymat encodé dans ``core.benchmarking``.

Test d'existence : la constante ``BENCHMARK_MIN_COMPANIES`` doit être
présente, valoir 5 (le plancher légal), et l'aide ``strate_publiable``
doit refuser toute strate en dessous de ce plancher — pour que NTDATA46/47
(collecte + restitution de benchmarks inter-tenants) aient un point d'import
unique à respecter dès leur premier jour."""
from django.test import SimpleTestCase

from core import benchmarking


class BenchmarkingMinCompaniesTests(SimpleTestCase):
    def test_constante_existe_et_vaut_cinq(self):
        self.assertTrue(hasattr(benchmarking, 'BENCHMARK_MIN_COMPANIES'))
        self.assertEqual(benchmarking.BENCHMARK_MIN_COMPANIES, 5)

    def test_docstring_module_mentionne_le_plancher(self):
        self.assertIn(
            'k-anonymat', (benchmarking.__doc__ or '').lower())

    def test_strate_sous_le_plancher_refusee(self):
        self.assertFalse(benchmarking.strate_publiable(4))

    def test_strate_au_plancher_publiable(self):
        self.assertTrue(benchmarking.strate_publiable(5))

    def test_strate_au_dessus_du_plancher_publiable(self):
        self.assertTrue(benchmarking.strate_publiable(12))
