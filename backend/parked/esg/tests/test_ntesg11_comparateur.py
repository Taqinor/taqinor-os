"""NTESG11 — Comparateur multi-période (N vs N-1).

Critère d'acceptation : la comparaison ignore proprement les indicateurs non
présents dans les deux périodes (jamais traités comme une variation de
+100 %/-100 %).
"""
from datetime import date

from django.test import TestCase

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory

from apps.esg.models import PeriodeReportingESG
from apps.esg.selectors import comparer_periodes


class ComparerPeriodesSelectorTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def _seed_indicateur(self, code, annee, valeur, pilier='environnement'):
        from apps.qhse.models import IndicateurESG

        return IndicateurESG.objects.create(
            company=self.company, code=code, libelle=f'Indicateur {code}',
            pilier=pilier, valeur=valeur, annee=annee)

    def _periode(self, libelle, annee):
        return PeriodeReportingESG.objects.create(
            company=self.company, libelle=libelle,
            date_debut=date(annee, 1, 1), date_fin=date(annee, 12, 31))

    def test_common_indicator_computes_variation(self):
        self._seed_indicateur('E1', 2025, 100)
        self._seed_indicateur('E1', 2026, 120)
        p2025 = self._periode('2025', 2025)
        p2026 = self._periode('2026', 2026)

        resultat = comparer_periodes(p2025, p2026)
        lignes = resultat['piliers']['environnement']
        ligne_e1 = next(ligne for ligne in lignes if ligne['code'] == 'E1')
        self.assertTrue(ligne_e1['comparable'])
        self.assertEqual(ligne_e1['variation_abs'], 20.0)
        self.assertEqual(ligne_e1['variation_pct'], 20.0)

    def test_indicator_only_in_one_period_is_non_comparable(self):
        self._seed_indicateur('E2', 2026, 50)
        p2025 = self._periode('2025-b', 2025)
        p2026 = self._periode('2026-b', 2026)

        resultat = comparer_periodes(p2025, p2026)
        lignes = resultat['piliers']['environnement']
        ligne_e2 = next(ligne for ligne in lignes if ligne['code'] == 'E2')
        self.assertFalse(ligne_e2['comparable'])
        self.assertNotIn('variation_pct', ligne_e2)

    def test_no_data_returns_empty_piliers(self):
        p2025 = self._periode('2025-c', 2025)
        p2026 = self._periode('2026-c', 2026)
        resultat = comparer_periodes(p2025, p2026)
        self.assertEqual(resultat['piliers'], {})


class ComparerPeriodesApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/periodes-esg/'

    def _periode(self, libelle, annee, company=None):
        return PeriodeReportingESG.objects.create(
            company=company or self.company, libelle=libelle,
            date_debut=date(annee, 1, 1), date_fin=date(annee, 12, 31))

    def test_comparer_requires_both_params(self):
        r = self.client_as().get(f'{self.BASE}comparer/')
        self.assertEqual(r.status_code, 400)

    def test_comparer_scoped_to_company(self):
        p1 = self._periode('2025', 2025)
        p2 = self._periode('2026', 2026)
        r = self.client_as().get(
            f'{self.BASE}comparer/', {'reference': p1.id, 'periode': p2.id})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['periode_reference']['id'], p1.id)
        self.assertEqual(r.data['periode_n']['id'], p2.id)

    def test_comparer_rejects_foreign_period(self):
        p1 = self._periode('2025-d', 2025)
        foreign = self._periode('2026-foreign', 2026, company=self.other_company)
        r = self.client_as().get(
            f'{self.BASE}comparer/',
            {'reference': p1.id, 'periode': foreign.id})
        self.assertEqual(r.status_code, 404)
