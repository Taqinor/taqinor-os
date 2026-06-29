"""Tests PAIE24 — Taxe de formation professionnelle (charge PATRONALE, 1,6 %).

Couvre :
* ``formation_professionnelle_patronale`` — assiette = brut intégral (non
  plafonnée), taux patronal (défaut 1,6 %), non-affilié → 0, ``parametre``
  absent → 0, taux configurable par société.
* Intégration dans ``calculer_bulletin`` : le dict expose
  ``formation_professionnelle`` ; le montant entre dans ``charges_patronales`` ;
  une ligne EMPLOYEUR (type cotisation) apparaît sur le bulletin ; la charge
  patronale n'est JAMAIS déduite du net du salarié.
* Multi-tenant — chaque société applique son propre taux.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, Rubrique
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    formation_professionnelle_patronale,
)
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class FormationProCalculTests(TestCase):
    """PAIE24 — calcul de la charge patronale (non plafonnée, taux 1,6 %)."""

    def setUp(self):
        self.co = make_company('formpro-co')
        ensure_defaults(self.co)
        self.param = self.co.paie_parametres.first()

    def test_default_rate_seedee(self):
        """Le seed pose le taux légal par défaut (1,6 %)."""
        self.assertEqual(self.param.taux_formation_pro, Decimal('1.6'))

    def test_non_plafonnee_sur_brut_integral(self):
        # Brut 10000 (au-dessus du plafond CNSS 6000) → assiette = brut entier.
        self.assertEqual(
            formation_professionnelle_patronale(self.param, Decimal('10000')),
            Decimal('160.00'))  # 10000 × 1.6 %

    def test_sous_plafond_cnss(self):
        self.assertEqual(
            formation_professionnelle_patronale(self.param, Decimal('4000')),
            Decimal('64.00'))  # 4000 × 1.6 %

    def test_non_affilie_zero(self):
        self.assertEqual(
            formation_professionnelle_patronale(
                self.param, Decimal('5000'), affilie=False),
            Decimal('0.00'))

    def test_parametre_absent_zero(self):
        self.assertEqual(
            formation_professionnelle_patronale(None, Decimal('5000')),
            Decimal('0.00'))


class FormationProConfigurableTests(TestCase):
    """Le taux est configurable côté société (jamais codé en dur)."""

    def test_taux_configurable(self):
        co = make_company('formpro-cfg')
        ensure_defaults(co)
        param = co.paie_parametres.first()
        param.taux_formation_pro = Decimal('2')
        param.save()
        param.refresh_from_db()
        self.assertEqual(
            formation_professionnelle_patronale(param, Decimal('6000')),
            Decimal('120.00'))  # 6000 × 2 %

    def test_isolation_taux(self):
        co_a = make_company('formpro-iso-a')
        co_b = make_company('formpro-iso-b')
        ensure_defaults(co_a)
        ensure_defaults(co_b)
        param_b = co_b.paie_parametres.first()
        param_b.taux_formation_pro = Decimal('3')
        param_b.save()

        self.assertEqual(
            formation_professionnelle_patronale(
                co_a.paie_parametres.first(), Decimal('6000')),
            Decimal('96.00'))  # 6000 × 1.6 %
        self.assertEqual(
            formation_professionnelle_patronale(param_b, Decimal('6000')),
            Decimal('180.00'))  # 6000 × 3 %


class BulletinFormationProTests(TestCase):
    """Intégration au bulletin : charge patronale, ligne employeur, hors net."""

    def setUp(self):
        self.co = make_company('bull-formpro')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'FP1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_bulletin_expose_formation_professionnelle(self):
        res = calculer_bulletin(self.profil, self.periode)
        # Brut 10000 × 1.6 % (non plafonnée).
        self.assertEqual(res['formation_professionnelle'], Decimal('160.00'))

    def test_formation_pro_dans_charges_patronales(self):
        res = calculer_bulletin(self.profil, self.periode)
        # charges_patronales = CNSS pat + AMO pat + allocations familiales
        # + taxe de formation professionnelle.
        self.assertEqual(
            res['charges_patronales'],
            res['cnss_patronale'] + res['amo_patronale']
            + res['allocations_familiales']
            + res['formation_professionnelle'])

    def test_ligne_employeur_presente(self):
        res = calculer_bulletin(self.profil, self.periode)
        lignes_form = [
            ligne for ligne in res['lignes']
            if ligne['code'] == 'FORMATION_PRO'
        ]
        self.assertEqual(len(lignes_form), 1)
        ligne = lignes_form[0]
        self.assertEqual(ligne['type'], Rubrique.TYPE_COTISATION)
        self.assertEqual(ligne['montant'], Decimal('160.00'))

    def test_non_deduite_du_net(self):
        """La charge patronale ne réduit PAS le net à payer du salarié."""
        res = calculer_bulletin(self.profil, self.periode)
        attendu = (
            res['brut'] - res['cnss_salariale'] - res['amo_salariale']
            - res['cimr_salariale'] - res['ir'] - res['retenues']
        )
        self.assertEqual(res['net_a_payer'], attendu)
        # Le montant de la taxe de formation n'apparaît nulle part dans le net.
        self.assertNotIn(
            res['formation_professionnelle'],
            [res['net_a_payer'] - res['brut']])

    def test_non_affilie_cnss_pas_de_ligne(self):
        """Profil non affilié CNSS → aucune taxe de formation ni ligne."""
        self.profil.affilie_cnss = False
        self.profil.save()
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['formation_professionnelle'], Decimal('0.00'))
        codes = [ligne['code'] for ligne in res['lignes']]
        self.assertNotIn('FORMATION_PRO', codes)
