"""Tests PAIE5 — barème IR officiel + déduction pour charges de famille.

Couvre :
  * ``ir_bareme`` applique correctement la formule par tranche du barème 2026
    (taux × base − somme à déduire), jamais négatif ;
  * ``deduction_charges_famille`` = N × montant, plafonnée au nombre maximal
    de personnes à charge ;
  * ``compute_ir`` = barème(base) − déduction, jamais sous zéro : N personnes
    à charge réduisent l'IR de N × montant (capé au plafond) ;
  * les valeurs par défaut 2026 de la déduction familiale sont seedées
    (30 MAD/personne, plafond 6) et restent éditables ;
  * exposition des deux champs par le sérialiseur/endpoint.
"""
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.paie.models import BaremeIR, ParametrePaie
from apps.paie.services import (
    DATE_EFFET_2026,
    compute_ir,
    deduction_charges_famille,
    ensure_defaults,
    ir_bareme,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class IRBaremeTests(TestCase):
    """Le barème par tranche (sans charges de famille)."""

    def setUp(self):
        self.co = make_company('paie-ir-bareme', 'A')
        ensure_defaults(self.co)
        self.bareme = BaremeIR.objects.get(company=self.co)

    def test_exonere_first_tranche(self):
        # Tranche 0–2500 @ 0 % : IR nul.
        self.assertEqual(ir_bareme(self.bareme, Decimal('2000')),
                         Decimal('0.00'))

    def test_below_first_borne_is_zero(self):
        self.assertEqual(ir_bareme(self.bareme, Decimal('0')), Decimal('0.00'))

    def test_tranche_10_percent(self):
        # 3000 dans la tranche 10 % : 3000 × 10 % − 250 = 50.
        self.assertEqual(ir_bareme(self.bareme, Decimal('3000')),
                         Decimal('50.00'))

    def test_tranche_20_percent(self):
        # 4500 dans la tranche 20 % : 4500 × 20 % − 666.67 = 233.33.
        self.assertEqual(ir_bareme(self.bareme, Decimal('4500')),
                         Decimal('233.33'))

    def test_top_tranche_38_percent(self):
        # 20000 dans la tranche marginale 38 % : 20000 × 38 % − 2033.33 = 5566.67.
        self.assertEqual(ir_bareme(self.bareme, Decimal('20000')),
                         Decimal('5566.67'))

    def test_bareme_never_negative(self):
        # Bas de tranche : la formule ne descend jamais sous zéro.
        self.assertGreaterEqual(ir_bareme(self.bareme, Decimal('2501')),
                                Decimal('0.00'))


class DeductionChargesFamilleTests(TestCase):
    """La déduction pour charges de famille (montant × nb, plafonnée)."""

    def setUp(self):
        self.co = make_company('paie-ded-famille', 'A')
        ensure_defaults(self.co)
        self.param = ParametrePaie.objects.get(company=self.co)

    def test_zero_dependents(self):
        self.assertEqual(
            deduction_charges_famille(self.param, 0), Decimal('0.00'))

    def test_three_dependents(self):
        # 3 × 30 = 90.
        self.assertEqual(
            deduction_charges_famille(self.param, 3), Decimal('90.00'))

    def test_capped_at_plafond(self):
        # 10 personnes mais plafond 6 → 6 × 30 = 180.
        self.assertEqual(
            deduction_charges_famille(self.param, 10), Decimal('180.00'))

    def test_exactly_at_plafond(self):
        self.assertEqual(
            deduction_charges_famille(self.param, 6), Decimal('180.00'))

    def test_negative_treated_as_zero(self):
        self.assertEqual(
            deduction_charges_famille(self.param, -2), Decimal('0.00'))

    def test_respects_founder_edited_values(self):
        # Le fondateur édite le montant et le plafond → la déduction suit.
        self.param.deduction_par_personne_a_charge = Decimal('41.67')
        self.param.plafond_personnes_a_charge = 4
        self.param.save()
        # 3 personnes : 3 × 41.67 = 125.01.
        self.assertEqual(
            deduction_charges_famille(self.param, 3), Decimal('125.01'))
        # 9 personnes mais plafond 4 : 4 × 41.67 = 166.68.
        self.assertEqual(
            deduction_charges_famille(self.param, 9), Decimal('166.68'))


class ComputeIRTests(TestCase):
    """IR net = barème(base) − déduction charges de famille (≥ 0)."""

    def setUp(self):
        self.co = make_company('paie-compute-ir', 'A')
        ensure_defaults(self.co)
        self.bareme = BaremeIR.objects.get(company=self.co)
        self.param = ParametrePaie.objects.get(company=self.co)

    def test_no_dependents_equals_bareme(self):
        base = Decimal('20000')
        self.assertEqual(
            compute_ir(base, self.bareme, self.param, 0),
            ir_bareme(self.bareme, base))

    def test_n_dependents_reduce_ir_by_n_times_montant(self):
        # 20000 → IR brut 5566.67 ; 3 personnes à charge → −90 = 5476.67.
        base = Decimal('20000')
        brut = ir_bareme(self.bareme, base)
        net = compute_ir(base, self.bareme, self.param, 3)
        self.assertEqual(brut - net, Decimal('90.00'))
        self.assertEqual(net, Decimal('5476.67'))

    def test_deduction_capped_at_plafond(self):
        # 12 personnes mais plafond 6 → réduction plafonnée à 180.
        base = Decimal('20000')
        brut = ir_bareme(self.bareme, base)
        net = compute_ir(base, self.bareme, self.param, 12)
        self.assertEqual(brut - net, Decimal('180.00'))

    def test_ir_never_negative(self):
        # Petit IR brut, beaucoup de personnes à charge : IR net plancher à 0.
        base = Decimal('3000')           # IR brut 50.00
        net = compute_ir(base, self.bareme, self.param, 6)  # déduction 180
        self.assertEqual(net, Decimal('0.00'))

    def test_exonere_base_stays_zero(self):
        # Revenu exonéré : IR net reste nul quel que soit le nb de personnes.
        self.assertEqual(
            compute_ir(Decimal('2000'), self.bareme, self.param, 4),
            Decimal('0.00'))


class FamilyDeductionDefaultsTests(TestCase):
    """Les valeurs par défaut 2026 de la déduction familiale sont seedées."""

    def setUp(self):
        self.co = make_company('paie-famille-defaults', 'A')

    def test_seed_sets_official_family_defaults(self):
        ensure_defaults(self.co)
        p = ParametrePaie.objects.get(company=self.co, date_effet=DATE_EFFET_2026)
        self.assertEqual(p.deduction_par_personne_a_charge, Decimal('30.00'))
        self.assertEqual(p.plafond_personnes_a_charge, 6)

    def test_command_seeds_family_defaults(self):
        call_command('seed_paie_legaux', company='paie-famille-defaults',
                     stdout=StringIO())
        p = ParametrePaie.objects.get(company=self.co)
        self.assertEqual(p.deduction_par_personne_a_charge, Decimal('30.00'))
        self.assertEqual(p.plafond_personnes_a_charge, 6)

    def test_family_defaults_editable_and_preserved_on_reseed(self):
        ensure_defaults(self.co)
        p = ParametrePaie.objects.get(company=self.co)
        p.deduction_par_personne_a_charge = Decimal('50.00')
        p.plafond_personnes_a_charge = 4
        p.valide_par_fondateur = True
        p.save()
        ensure_defaults(self.co)            # re-seed
        p.refresh_from_db()
        self.assertEqual(p.deduction_par_personne_a_charge, Decimal('50.00'))
        self.assertEqual(p.plafond_personnes_a_charge, 4)
        self.assertTrue(p.valide_par_fondateur)


class FamilyDeductionApiTests(TestCase):
    """Les champs de déduction familiale sont exposés et éditables via l'API."""

    BASE = '/api/django/paie/parametres/'

    def setUp(self):
        self.co = make_company('paie-famille-api', 'A')
        self.user = make_user(self.co, 'paie-famille-api')

    def test_fields_exposed_after_seed(self):
        api = auth(self.user)
        api.post(self.BASE + 'seed-defaults/', {}, format='json')
        p = ParametrePaie.objects.get(company=self.co)
        resp = api.get(f'{self.BASE}{p.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['deduction_par_personne_a_charge'], '30.00')
        self.assertEqual(resp.data['plafond_personnes_a_charge'], 6)

    def test_founder_can_edit_family_params_via_patch(self):
        api = auth(self.user)
        api.post(self.BASE + 'seed-defaults/', {}, format='json')
        p = ParametrePaie.objects.get(company=self.co)
        resp = api.patch(
            f'{self.BASE}{p.id}/',
            {'deduction_par_personne_a_charge': '45',
             'plafond_personnes_a_charge': 5},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertEqual(p.deduction_par_personne_a_charge, Decimal('45.00'))
        self.assertEqual(p.plafond_personnes_a_charge, 5)
