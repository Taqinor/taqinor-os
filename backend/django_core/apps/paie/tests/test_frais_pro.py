"""Tests PAIE21 — Frais professionnels & net imposable.

Les frais professionnels sont une déduction marocaine assise sur le BRUT
IMPOSABLE, qui réduit le net imposable AVANT le calcul de l'IR :

* barème 2026 (défauts ``ParametrePaie``) : 35 % du brut imposable plafonné à
  2 500 MAD/mois lorsque le brut imposable n'excède pas le seuil (6 500
  MAD/mois) ; 25 % plafonné à 2 916,67 MAD/mois au-delà du seuil ;
* le net imposable = brut imposable − (CNSS + AMO + CIMR + frais pro) ;
* l'IR est calculé sur ce net imposable RÉDUIT (pas sur le brut imposable).

Couvre :
* taux bas (brut ≤ seuil) appliqué sans atteindre le plafond ;
* plafond bas appliqué quand 35 % dépasse 2 500 ;
* taux haut (brut > seuil) appliqué sans atteindre le plafond ;
* plafond haut appliqué quand 25 % dépasse 2 916,67 ;
* les frais pro RÉDUISENT le net imposable (vs un paramètre à 0 %) ;
* l'IR est calculé sur la base réduite (moins d'IR avec frais pro) ;
* multi-tenant — chaque société utilise SON propre ``ParametrePaie``.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ParametrePaie, PeriodePaie
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    parametre_en_vigueur,
)
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


# Le paramètre en vigueur est résolu au 1er du mois de la période (juin 2026),
# comme le fait ``calculer_bulletin``.
JOUR = date(2026, 6, 1)


class FraisProBulletinTests(TestCase):
    """Intégration ``calculer_bulletin`` — barème par défaut (35/25 %)."""

    def setUp(self):
        self.co = make_company('fp-bull')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_defaut_taux_bas_sous_plafond(self):
        # Brut imposable 4000 ≤ seuil (6500) → 35 % = 1400 < plafond 2500.
        dossier = make_dossier(self.co, 'FPB')
        profil = make_profil(self.co, dossier, Decimal('4000'))
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['frais_professionnels'], Decimal('1400.00'))

    def test_taux_bas_atteint_le_plafond(self):
        # Brut imposable 6500 (= seuil) → 35 % = 2275 < 2500, encore sous plafond.
        # Brut imposable 6000 → 35 % = 2100. Pour heurter le plafond bas il faut
        # 35 % × brut > 2500, i.e. brut > 7142.86 — mais > 6500 bascule sur le
        # taux haut. On vérifie donc le plafond bas en abaissant le seuil.
        param = parametre_en_vigueur(self.co, JOUR)
        param.seuil_frais_pro = Decimal('100000')  # tout passe par le taux bas
        param.save()
        dossier = make_dossier(self.co, 'FPCAP')
        profil = make_profil(self.co, dossier, Decimal('10000'))
        res = calculer_bulletin(profil, self.periode)
        # 35 % × 10000 = 3500 > plafond bas 2500 → plafonné.
        self.assertEqual(res['frais_professionnels'], Decimal('2500.00'))

    def test_taux_haut_sous_plafond(self):
        # Brut imposable 10000 > seuil (6500) → 25 % = 2500 < plafond 2916.67.
        dossier = make_dossier(self.co, 'FPH')
        profil = make_profil(self.co, dossier, Decimal('10000'))
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['frais_professionnels'], Decimal('2500.00'))

    def test_taux_haut_atteint_le_plafond(self):
        # Brut imposable 15000 > seuil → 25 % = 3750 > plafond haut 2916.67.
        dossier = make_dossier(self.co, 'FPHCAP')
        profil = make_profil(self.co, dossier, Decimal('15000'))
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['frais_professionnels'], Decimal('2916.67'))

    def test_frais_pro_reduit_net_imposable(self):
        """Frais pro = 0 % → net imposable PLUS HAUT qu'avec le barème défaut."""
        dossier_on = make_dossier(self.co, 'FPON')
        profil_on = make_profil(self.co, dossier_on, Decimal('10000'))
        res_on = calculer_bulletin(profil_on, self.periode)

        # Société sœur avec frais pro désactivés (taux 0, plafond 0).
        co_off = make_company('fp-off')
        ensure_defaults(co_off)
        param_off = parametre_en_vigueur(co_off, JOUR)
        param_off.taux_frais_pro_bas = Decimal('0')
        param_off.taux_frais_pro_haut = Decimal('0')
        param_off.plafond_frais_pro_bas = Decimal('0')
        param_off.plafond_frais_pro_haut = Decimal('0')
        param_off.save()
        periode_off = PeriodePaie.objects.create(
            company=co_off, annee=2026, mois=6)
        dossier_off = make_dossier(co_off, 'FPOFF')
        profil_off = make_profil(co_off, dossier_off, Decimal('10000'))
        res_off = calculer_bulletin(profil_off, periode_off)

        self.assertEqual(res_off['frais_professionnels'], Decimal('0.00'))
        self.assertGreater(res_on['frais_professionnels'], Decimal('0'))
        # Le net imposable AVEC frais pro est plus bas que sans.
        self.assertLess(res_on['net_imposable'], res_off['net_imposable'])
        # L'écart vaut exactement les frais professionnels.
        self.assertEqual(
            res_off['net_imposable'] - res_on['net_imposable'],
            res_on['frais_professionnels'])

    def test_ir_calcule_sur_base_reduite(self):
        """L'IR est assis sur le net imposable réduit : frais pro → moins d'IR."""
        dossier_on = make_dossier(self.co, 'IRON')
        profil_on = make_profil(self.co, dossier_on, Decimal('10000'))
        res_on = calculer_bulletin(profil_on, self.periode)

        co_off = make_company('fp-ir-off')
        ensure_defaults(co_off)
        param_off = parametre_en_vigueur(co_off, JOUR)
        param_off.taux_frais_pro_bas = Decimal('0')
        param_off.taux_frais_pro_haut = Decimal('0')
        param_off.plafond_frais_pro_bas = Decimal('0')
        param_off.plafond_frais_pro_haut = Decimal('0')
        param_off.save()
        periode_off = PeriodePaie.objects.create(
            company=co_off, annee=2026, mois=6)
        dossier_off = make_dossier(co_off, 'IROFF')
        profil_off = make_profil(co_off, dossier_off, Decimal('10000'))
        res_off = calculer_bulletin(profil_off, periode_off)

        # Avec frais pro la base imposable est plus basse → IR strictement plus
        # bas (à 10000 le revenu reste dans une tranche imposable non nulle).
        self.assertLess(res_on['net_imposable'], res_off['net_imposable'])
        self.assertLess(res_on['ir'], res_off['ir'])

    def test_net_imposable_chaine_de_calcul(self):
        """net_imposable = brut imposable − CNSS − AMO − CIMR − frais pro."""
        dossier = make_dossier(self.co, 'CHAIN')
        profil = make_profil(self.co, dossier, Decimal('10000'))
        res = calculer_bulletin(profil, self.periode)
        attendu = (
            res['brut_imposable']
            - res['cnss_salariale']
            - res['amo_salariale']
            - res['cimr_salariale']
            - res['frais_professionnels']
        )
        self.assertEqual(res['net_imposable'], attendu)

    def test_scoping_parametre_par_societe(self):
        """Chaque société applique SON propre barème de frais professionnels."""
        # Société A : barème par défaut (25 % au-delà du seuil).
        dossier_a = make_dossier(self.co, 'SCA')
        profil_a = make_profil(self.co, dossier_a, Decimal('10000'))
        res_a = calculer_bulletin(profil_a, self.periode)
        self.assertEqual(res_a['frais_professionnels'], Decimal('2500.00'))

        # Société B : taux haut réduit à 10 % → 10 % × 10000 = 1000.
        co_b = make_company('fp-scope-b')
        ensure_defaults(co_b)
        param_b = parametre_en_vigueur(co_b, JOUR)
        param_b.taux_frais_pro_haut = Decimal('10')
        param_b.save()
        periode_b = PeriodePaie.objects.create(
            company=co_b, annee=2026, mois=6)
        dossier_b = make_dossier(co_b, 'SCB')
        profil_b = make_profil(co_b, dossier_b, Decimal('10000'))
        res_b = calculer_bulletin(profil_b, periode_b)
        self.assertEqual(res_b['frais_professionnels'], Decimal('1000.00'))


class FraisProParamDefautTests(TestCase):
    """Le barème de frais professionnels par défaut est bien semé (PAIE21)."""

    def test_ensure_defaults_pose_le_bareme(self):
        co = make_company('fp-defaults')
        ensure_defaults(co)
        param = ParametrePaie.objects.filter(company=co).first()
        self.assertIsNotNone(param)
        self.assertEqual(param.taux_frais_pro_bas, Decimal('35.000'))
        self.assertEqual(param.plafond_frais_pro_bas, Decimal('2500.00'))
        self.assertEqual(param.taux_frais_pro_haut, Decimal('25.000'))
        self.assertEqual(param.plafond_frais_pro_haut, Decimal('2916.67'))
        self.assertEqual(param.seuil_frais_pro, Decimal('6500.00'))
