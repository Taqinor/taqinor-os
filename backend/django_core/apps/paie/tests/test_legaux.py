"""Tests PAIE3 — valeurs légales 2026 par défaut + validation fondateur.

Couvre :
  * ``ensure_defaults`` seed les bonnes valeurs 2026 (CNSS/AMO/plafond/frais
    pro + barème IR à 6 tranches) ;
  * idempotence : un re-seed ne crée aucun doublon et ne touche pas une valeur
    éditée ;
  * isolation multi-société (le seed d'une société n'affecte pas l'autre) ;
  * ``valide_par_fondateur`` part à False ;
  * la commande ``seed_paie_legaux`` et l'action API ``seed-defaults``.
"""
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.paie.models import BaremeIR, ParametrePaie, TrancheIR
from apps.paie.services import (
    DATE_EFFET_2026,
    PARAMETRES_DEFAUT_2026,
    TRANCHES_IR_2026,
    ensure_defaults,
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


class EnsureDefaultsTests(TestCase):
    def setUp(self):
        self.co = make_company('paie-legaux-a', 'A')

    def test_seed_creates_expected_2026_parametres(self):
        created = ensure_defaults(self.co)
        self.assertEqual(created['parametre'], 1)

        p = ParametrePaie.objects.get(company=self.co, date_effet=DATE_EFFET_2026)
        # Plafond + taux CNSS/AMO + frais pro = valeurs 2026 attendues.
        self.assertEqual(p.plafond_cnss, Decimal('6000.00'))
        self.assertEqual(p.taux_cnss_salarial, Decimal('4.480'))
        self.assertEqual(p.taux_amo_salarial, Decimal('2.260'))
        self.assertEqual(p.taux_formation_pro, Decimal('1.600'))
        self.assertEqual(p.seuil_frais_pro, Decimal('6500.00'))
        self.assertEqual(p.taux_frais_pro_bas, Decimal('35.000'))
        self.assertEqual(p.plafond_frais_pro_bas, Decimal('2500.00'))
        self.assertEqual(p.taux_frais_pro_haut, Decimal('25.000'))
        self.assertEqual(p.plafond_frais_pro_haut, Decimal('2916.67'))

    def test_seed_creates_expected_2026_bareme_ir(self):
        created = ensure_defaults(self.co)
        self.assertEqual(created['bareme'], 1)
        self.assertEqual(created['tranches'], 6)

        bareme = BaremeIR.objects.get(company=self.co, date_effet=DATE_EFFET_2026)
        tranches = list(bareme.tranches.order_by('ordre'))
        self.assertEqual(len(tranches), 6)
        # Première tranche exonérée 0–2500 @ 0 %.
        self.assertEqual(tranches[0].borne_min, Decimal('0.00'))
        self.assertEqual(tranches[0].borne_max, Decimal('2500.00'))
        self.assertEqual(tranches[0].taux, Decimal('0.000'))
        # Tranche marginale supérieure : 38 %, sans plafond.
        self.assertEqual(tranches[-1].taux, Decimal('38.000'))
        self.assertIsNone(tranches[-1].borne_max)
        # La somme à déduire de la dernière tranche correspond au barème.
        self.assertEqual(tranches[-1].somme_a_deduire, Decimal('2033.33'))
        # Les bornes/taux des 6 tranches sont exactement ceux du barème 2026.
        expected = [(t[0], t[1], t[2]) for t in TRANCHES_IR_2026]
        got = [(t.borne_min, t.borne_max, t.taux) for t in tranches]
        for (e_min, e_max, e_taux), (g_min, g_max, g_taux) in zip(expected, got):
            self.assertEqual(g_min, e_min)
            self.assertEqual(g_taux, e_taux)
            if e_max is None:
                self.assertIsNone(g_max)
            else:
                self.assertEqual(g_max, e_max)

    def test_valide_par_fondateur_defaults_false(self):
        ensure_defaults(self.co)
        p = ParametrePaie.objects.get(company=self.co)
        b = BaremeIR.objects.get(company=self.co)
        self.assertFalse(p.valide_par_fondateur)
        self.assertFalse(b.valide_par_fondateur)

    def test_seed_is_idempotent(self):
        ensure_defaults(self.co)
        again = ensure_defaults(self.co)
        # Deuxième passage : rien créé.
        self.assertEqual(again, {'parametre': 0, 'bareme': 0, 'tranches': 0})
        self.assertEqual(
            ParametrePaie.objects.filter(company=self.co).count(), 1)
        self.assertEqual(BaremeIR.objects.filter(company=self.co).count(), 1)
        self.assertEqual(TrancheIR.objects.filter(company=self.co).count(), 6)

    def test_reseed_preserves_founder_edits(self):
        ensure_defaults(self.co)
        # Le fondateur surcharge & valide.
        p = ParametrePaie.objects.get(company=self.co)
        p.plafond_cnss = Decimal('7000.00')
        p.valide_par_fondateur = True
        p.save()
        # Re-seed : la ligne existante n'est PAS écrasée.
        ensure_defaults(self.co)
        p.refresh_from_db()
        self.assertEqual(p.plafond_cnss, Decimal('7000.00'))
        self.assertTrue(p.valide_par_fondateur)

    def test_returned_defaults_match_constant_table(self):
        # Garde-fou : le dict de constantes reste cohérent avec ce qui est posé.
        ensure_defaults(self.co)
        p = ParametrePaie.objects.get(company=self.co)
        for field, value in PARAMETRES_DEFAUT_2026.items():
            self.assertEqual(getattr(p, field), value, field)


class MultiTenantSeedTests(TestCase):
    def test_seed_is_company_scoped(self):
        co_a = make_company('paie-legaux-x', 'X')
        co_b = make_company('paie-legaux-y', 'Y')
        ensure_defaults(co_a)
        # B n'a rien tant qu'on ne le seed pas.
        self.assertEqual(ParametrePaie.objects.filter(company=co_b).count(), 0)
        self.assertEqual(BaremeIR.objects.filter(company=co_b).count(), 0)
        ensure_defaults(co_b)
        # Chaque société a exactement son propre jeu.
        self.assertEqual(ParametrePaie.objects.filter(company=co_a).count(), 1)
        self.assertEqual(ParametrePaie.objects.filter(company=co_b).count(), 1)
        self.assertEqual(TrancheIR.objects.filter(company=co_a).count(), 6)
        self.assertEqual(TrancheIR.objects.filter(company=co_b).count(), 6)


class SeedCommandTests(TestCase):
    def test_command_seeds_all_companies_idempotently(self):
        co_a = make_company('paie-cmd-a', 'A')
        co_b = make_company('paie-cmd-b', 'B')
        out = StringIO()
        call_command('seed_paie_legaux', stdout=out)
        self.assertEqual(ParametrePaie.objects.filter(company=co_a).count(), 1)
        self.assertEqual(ParametrePaie.objects.filter(company=co_b).count(), 1)
        # Re-run : toujours une seule ligne par société.
        call_command('seed_paie_legaux', stdout=StringIO())
        self.assertEqual(ParametrePaie.objects.filter(company=co_a).count(), 1)
        self.assertEqual(BaremeIR.objects.filter(company=co_b).count(), 1)

    def test_command_single_company(self):
        co_a = make_company('paie-cmd-solo-a', 'A')
        co_b = make_company('paie-cmd-solo-b', 'B')
        call_command('seed_paie_legaux', company='paie-cmd-solo-a',
                     stdout=StringIO())
        self.assertEqual(ParametrePaie.objects.filter(company=co_a).count(), 1)
        self.assertEqual(ParametrePaie.objects.filter(company=co_b).count(), 0)


class SeedDefaultsApiTests(TestCase):
    BASE = '/api/django/paie/parametres/'

    def setUp(self):
        self.co = make_company('paie-api-seed', 'A')
        self.user = make_user(self.co, 'paie-api-seed')

    def test_seed_defaults_action_forces_company_and_is_idempotent(self):
        api = auth(self.user)
        resp = api.post(self.BASE + 'seed-defaults/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['parametre'], 1)
        # Toujours scopé à la société de l'utilisateur (jamais du corps).
        p = ParametrePaie.objects.get(company=self.co)
        self.assertEqual(p.company, self.co)
        self.assertFalse(p.valide_par_fondateur)
        # Re-jouée : rien de neuf.
        resp2 = api.post(self.BASE + 'seed-defaults/', {}, format='json')
        self.assertEqual(resp2.data['parametre'], 0)
        self.assertEqual(ParametrePaie.objects.filter(company=self.co).count(), 1)

    def test_founder_can_validate_via_patch(self):
        api = auth(self.user)
        api.post(self.BASE + 'seed-defaults/', {}, format='json')
        p = ParametrePaie.objects.get(company=self.co)
        resp = api.patch(
            f'{self.BASE}{p.id}/',
            {'valide_par_fondateur': True, 'plafond_cnss': '7000'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertTrue(p.valide_par_fondateur)
        self.assertEqual(p.plafond_cnss, Decimal('7000.00'))
