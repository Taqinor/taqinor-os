"""Tests PAIE19 — Cotisation AMO NON PLAFONNÉE, parts salariale ET patronale.

Couvre :
* ``amo_salariale`` / ``amo_patronale`` — assiette = brut INTÉGRAL (aucun
  plafond, contrairement à la CNSS), taux salarial vs patronal, non-affilié → 0,
  ``parametre`` absent → 0.
* Intégration dans ``calculer_bulletin`` : le dict expose ``amo_patronale`` et
  l'agrège dans ``charges_patronales`` (avec la part patronale CNSS) ; la part
  patronale AMO n'entre PAS dans le net du salarié.
* Multi-tenant — chaque société applique son propre taux AMO patronal.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie
from apps.paie.services import (
    amo_patronale,
    amo_salariale,
    calculer_bulletin,
    ensure_defaults,
)
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class AmoCotisationTests(TestCase):
    """PAIE19 — AMO sans plafond : part salariale & patronale."""

    def setUp(self):
        self.co = make_company('amo-co')
        ensure_defaults(self.co)
        self.param = self.co.paie_parametres.first()
        # Défauts 2026 : AMO salarial 2.26 %, patronal 2.26 %.

    def test_pas_de_plafond(self):
        # AMO porte sur le brut INTÉGRAL, même bien au-delà du plafond CNSS.
        self.assertEqual(
            amo_salariale(self.param, Decimal('10000')),
            Decimal('226.00'))  # 10000 × 2.26 %
        self.assertEqual(
            amo_patronale(self.param, Decimal('10000')),
            Decimal('226.00'))

    def test_brut_eleve_pas_de_cap(self):
        # Brut 50 000 : l'AMO ne se plafonne jamais.
        self.assertEqual(
            amo_salariale(self.param, Decimal('50000')),
            Decimal('1130.00'))  # 50000 × 2.26 %

    def test_non_affilie_zero(self):
        self.assertEqual(
            amo_salariale(self.param, Decimal('8000'), affilie=False),
            Decimal('0.00'))
        self.assertEqual(
            amo_patronale(self.param, Decimal('8000'), affilie=False),
            Decimal('0.00'))

    def test_parametre_absent_zero(self):
        self.assertEqual(amo_salariale(None, Decimal('8000')), Decimal('0.00'))
        self.assertEqual(amo_patronale(None, Decimal('8000')), Decimal('0.00'))


class BulletinAmoTests(TestCase):
    """Intégration : le bulletin expose la part patronale AMO et l'agrège."""

    def setUp(self):
        self.co = make_company('bull-amo')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'AM1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_bulletin_expose_amo_patronale(self):
        res = calculer_bulletin(self.profil, self.periode)
        # Brut 10000 : AMO sur 10000 (non plafonnée).
        self.assertEqual(res['amo_salariale'], Decimal('226.00'))
        self.assertEqual(res['amo_patronale'], Decimal('226.00'))
        # charges_patronales = CNSS patronale (538.80) + AMO patronale (226.00).
        self.assertEqual(res['charges_patronales'], Decimal('764.80'))

    def test_charges_patronales_hors_net(self):
        """La part patronale AMO ne réduit PAS le net à payer du salarié."""
        res = calculer_bulletin(self.profil, self.periode)
        attendu = (
            res['brut'] - res['cnss_salariale'] - res['amo_salariale']
            - res['cimr_salariale'] - res['ir'] - res['retenues']
        )
        self.assertEqual(res['net_a_payer'], attendu)

    def test_non_affilie_amo_pas_de_cotisation(self):
        self.profil.affilie_amo = False
        self.profil.save()
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['amo_salariale'], Decimal('0.00'))
        self.assertEqual(res['amo_patronale'], Decimal('0.00'))
        # Reste la CNSS patronale dans les charges.
        self.assertEqual(res['charges_patronales'], res['cnss_patronale'])


class AmoIsolationTests(TestCase):
    """Chaque société applique son propre taux AMO patronal."""

    def test_isolation_taux(self):
        co_a = make_company('amo-iso-a')
        co_b = make_company('amo-iso-b')
        ensure_defaults(co_a)
        ensure_defaults(co_b)
        param_b = co_b.paie_parametres.first()
        param_b.taux_amo_patronal = Decimal('5')
        param_b.save()

        self.assertEqual(
            amo_patronale(co_a.paie_parametres.first(), Decimal('10000')),
            Decimal('226.00'))  # 10000 × 2.26 %
        self.assertEqual(
            amo_patronale(param_b, Decimal('10000')),
            Decimal('500.00'))  # 10000 × 5 %
