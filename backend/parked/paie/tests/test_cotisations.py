"""Tests PAIE18 — Cotisation CNSS PLAFONNÉE, parts salariale ET patronale.

(PAIE19 ajoute plus bas les tests AMO sans plafond.)

Couvre :
* ``cnss_salariale`` / ``cnss_patronale`` — assiette PLAFONNÉE à ``plafond_cnss``,
  taux salarial vs patronal, respect du plafond, non-affilié → 0,
  ``parametre`` absent → 0.
* Intégration dans ``calculer_bulletin`` : le dict expose ``cnss_patronale`` et
  ``charges_patronales`` ; la part patronale n'entre PAS dans le net du salarié.
* Multi-tenant — chaque société applique son propre taux/plafond.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie
from apps.paie.services import (
    calculer_bulletin,
    cnss_patronale,
    cnss_salariale,
    ensure_defaults,
)
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class CnssCotisationTests(TestCase):
    """PAIE18 — CNSS plafonnée : part salariale & patronale."""

    def setUp(self):
        self.co = make_company('cnss-co')
        ensure_defaults(self.co)
        self.param = self.co.paie_parametres.first()
        # Défauts 2026 : plafond 6000, salarial 4.48 %, patronal 8.98 %.

    def test_sous_plafond(self):
        # Brut 4000 < plafond 6000 → assiette = 4000.
        self.assertEqual(
            cnss_salariale(self.param, Decimal('4000')),
            Decimal('179.20'))  # 4000 × 4.48 %
        self.assertEqual(
            cnss_patronale(self.param, Decimal('4000')),
            Decimal('359.20'))  # 4000 × 8.98 %

    def test_au_dessus_plafond_assiette_plafonnee(self):
        # Brut 10000 > plafond 6000 → assiette plafonnée à 6000.
        self.assertEqual(
            cnss_salariale(self.param, Decimal('10000')),
            Decimal('268.80'))  # 6000 × 4.48 %
        self.assertEqual(
            cnss_patronale(self.param, Decimal('10000')),
            Decimal('538.80'))  # 6000 × 8.98 %

    def test_non_affilie_zero(self):
        self.assertEqual(
            cnss_salariale(self.param, Decimal('5000'), affilie=False),
            Decimal('0.00'))
        self.assertEqual(
            cnss_patronale(self.param, Decimal('5000'), affilie=False),
            Decimal('0.00'))

    def test_parametre_absent_zero(self):
        self.assertEqual(cnss_salariale(None, Decimal('5000')), Decimal('0.00'))
        self.assertEqual(cnss_patronale(None, Decimal('5000')), Decimal('0.00'))


class BulletinCnssTests(TestCase):
    """Intégration : le bulletin expose la part patronale CNSS sans toucher le net."""

    def setUp(self):
        self.co = make_company('bull-cnss')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'CN1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_bulletin_expose_cnss_patronale(self):
        res = calculer_bulletin(self.profil, self.periode)
        # Brut 10000 : CNSS plafonnée à 6000.
        self.assertEqual(res['cnss_salariale'], Decimal('268.80'))
        self.assertEqual(res['cnss_patronale'], Decimal('538.80'))
        # charges_patronales agrège la CNSS patronale + l'AMO patronale
        # (PAIE19) + les allocations familiales (PAIE23) + la taxe de formation
        # professionnelle (PAIE24) + tout autre poste patronal — assertion
        # robuste à l'ajout.
        self.assertEqual(
            res['charges_patronales'],
            res['cnss_patronale'] + res['amo_patronale']
            + res['allocations_familiales']
            + res['formation_professionnelle'])
        self.assertGreaterEqual(res['charges_patronales'], Decimal('538.80'))

    def test_charges_patronales_hors_net(self):
        """La part patronale CNSS ne réduit PAS le net à payer du salarié."""
        res = calculer_bulletin(self.profil, self.periode)
        attendu = (
            res['brut'] - res['cnss_salariale'] - res['amo_salariale']
            - res['cimr_salariale'] - res['ir'] - res['retenues']
        )
        self.assertEqual(res['net_a_payer'], attendu)


class CnssIsolationTests(TestCase):
    """Chaque société applique son propre taux CNSS patronal."""

    def test_isolation_taux(self):
        co_a = make_company('cnss-iso-a')
        co_b = make_company('cnss-iso-b')
        ensure_defaults(co_a)
        ensure_defaults(co_b)
        param_b = co_b.paie_parametres.first()
        param_b.taux_cnss_patronal = Decimal('10')
        param_b.save()

        self.assertEqual(
            cnss_patronale(co_a.paie_parametres.first(), Decimal('6000')),
            Decimal('538.80'))  # 6000 × 8.98 %
        self.assertEqual(
            cnss_patronale(param_b, Decimal('6000')),
            Decimal('600.00'))  # 6000 × 10 %
