"""Tests PAIE15 — Prime d'ancienneté barème (5/10/15/20/25 %).

Couvre :
* ``calculer_anciennete_annees`` — calcul exact des années complètes à une
  date donnée (cas limites : date nulle, même jour, veille d'anniversaire,
  jour d'anniversaire, années bissextiles).
* ``taux_anciennete`` — chaque palier du barème standard (0 / 5 / 10 / 15 /
  20 / 25 %) est renvoyé pour la bonne tranche d'ancienneté.
* ``calculer_prime_anciennete`` — la prime est bien ``base × taux / 100``
  arrondie au centime ; retourne 0 quand le taux est 0.
* ``calculer_bulletin`` — la prime d'ancienneté apparaît dans le brut et dans
  les lignes du bulletin ; un salarié sans ancienneté suffisante ne voit
  aucun effet.
* Personnalisation du barème sur ``ParametrePaie`` — les taux et seuils
  éditables sont pris en compte.
* Multi-tenant — isolation société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ParametrePaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_anciennete_annees,
    calculer_bulletin,
    calculer_prime_anciennete,
    ensure_defaults,
    taux_anciennete,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────

def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_dossier(company, matricule='E1', date_embauche=None):
    return DossierEmploye.objects.create(
        company=company,
        matricule=matricule,
        nom='Test',
        prenom='Anciennete',
        date_embauche=date_embauche,
    )


def make_profil(company, dossier, salaire_base=Decimal('10000')):
    return ProfilPaie.objects.create(
        company=company,
        employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=salaire_base,
        affilie_cnss=True,
        affilie_amo=True,
    )


def make_periode(company, annee=2026, mois=6):
    return PeriodePaie.objects.create(company=company, annee=annee, mois=mois)


def get_param(company):
    return ParametrePaie.objects.get(company=company, date_effet='2026-01-01')


# ── calculer_anciennete_annees ─────────────────────────────────────────────

class CalculerAncienneteAnneesTests(TestCase):
    """Calcul du nombre d'années complètes d'ancienneté."""

    def test_date_nulle_renvoie_zero(self):
        self.assertEqual(calculer_anciennete_annees(None, date(2026, 6, 1)), 0)

    def test_date_future_renvoie_zero(self):
        """Embauche future → ancienneté nulle."""
        self.assertEqual(
            calculer_anciennete_annees(date(2027, 1, 1), date(2026, 6, 1)), 0)

    def test_meme_jour_zero_ans(self):
        """Le jour même de l'embauche → 0 années complètes."""
        self.assertEqual(
            calculer_anciennete_annees(date(2026, 6, 1), date(2026, 6, 1)), 0)

    def test_exactement_un_an(self):
        """L'anniversaire exact → 1 année complète."""
        self.assertEqual(
            calculer_anciennete_annees(date(2025, 6, 1), date(2026, 6, 1)), 1)

    def test_veille_anniversaire_moins_un(self):
        """La veille de l'anniversaire → n-1 années."""
        self.assertEqual(
            calculer_anciennete_annees(date(2023, 6, 2), date(2026, 6, 1)), 2)

    def test_2_ans_exactement(self):
        self.assertEqual(
            calculer_anciennete_annees(date(2024, 6, 1), date(2026, 6, 1)), 2)

    def test_5_ans(self):
        self.assertEqual(
            calculer_anciennete_annees(date(2021, 1, 15), date(2026, 6, 1)), 5)

    def test_12_ans(self):
        self.assertEqual(
            calculer_anciennete_annees(date(2014, 3, 1), date(2026, 6, 1)), 12)

    def test_20_ans(self):
        self.assertEqual(
            calculer_anciennete_annees(date(2006, 1, 1), date(2026, 6, 1)), 20)

    def test_25_ans(self):
        self.assertEqual(
            calculer_anciennete_annees(date(2001, 1, 1), date(2026, 6, 1)), 25)

    def test_bissextile_28_fevrier(self):
        """Embauche le 29 fév (bissextile) : l'anniversaire en année non-biss
        est le 28 fév — on vérifie juste que la fonction ne plante pas."""
        annees = calculer_anciennete_annees(date(2000, 2, 29), date(2026, 6, 1))
        self.assertEqual(annees, 26)


# ── taux_anciennete ────────────────────────────────────────────────────────

class TauxAncienneteTests(TestCase):
    """Barème par palier — taux renvoyé pour chaque tranche."""

    def setUp(self):
        self.co = make_company('anc-taux')
        ensure_defaults(self.co)
        self.param = get_param(self.co)

    def test_zero_an_taux_nul(self):
        self.assertEqual(taux_anciennete(self.param, 0), Decimal('0'))

    def test_un_an_taux_nul(self):
        """Moins de 2 ans → 0 %."""
        self.assertEqual(taux_anciennete(self.param, 1), Decimal('0'))

    def test_2_ans_5_pct(self):
        self.assertEqual(taux_anciennete(self.param, 2), Decimal('5'))

    def test_4_ans_5_pct(self):
        """Encore dans la première tranche (2–4 ans)."""
        self.assertEqual(taux_anciennete(self.param, 4), Decimal('5'))

    def test_5_ans_10_pct(self):
        self.assertEqual(taux_anciennete(self.param, 5), Decimal('10'))

    def test_11_ans_10_pct(self):
        self.assertEqual(taux_anciennete(self.param, 11), Decimal('10'))

    def test_12_ans_15_pct(self):
        self.assertEqual(taux_anciennete(self.param, 12), Decimal('15'))

    def test_19_ans_15_pct(self):
        self.assertEqual(taux_anciennete(self.param, 19), Decimal('15'))

    def test_20_ans_20_pct(self):
        self.assertEqual(taux_anciennete(self.param, 20), Decimal('20'))

    def test_24_ans_20_pct(self):
        self.assertEqual(taux_anciennete(self.param, 24), Decimal('20'))

    def test_25_ans_25_pct(self):
        self.assertEqual(taux_anciennete(self.param, 25), Decimal('25'))

    def test_30_ans_25_pct(self):
        """Au-delà du seuil max → plafonné au taux max (25 %)."""
        self.assertEqual(taux_anciennete(self.param, 30), Decimal('25'))

    def test_parametre_none_renvoie_zero(self):
        self.assertEqual(taux_anciennete(None, 10), Decimal('0'))


# ── calculer_prime_anciennete ──────────────────────────────────────────────

class CalculerPrimeAncienneteTests(TestCase):
    """Calcul de la prime sur une base connue."""

    def setUp(self):
        self.co = make_company('anc-prime')
        ensure_defaults(self.co)
        self.param = get_param(self.co)
        self.dossier = make_dossier(self.co, 'P1')
        self.profil = make_profil(self.co, self.dossier)

    def test_2_ans_5_pct_de_10000(self):
        """10 000 × 5 % = 500 MAD."""
        prime = calculer_prime_anciennete(self.profil, Decimal('10000'), 2, self.param)
        self.assertEqual(prime, Decimal('500.00'))

    def test_5_ans_10_pct_de_8000(self):
        """8 000 × 10 % = 800 MAD."""
        prime = calculer_prime_anciennete(self.profil, Decimal('8000'), 5, self.param)
        self.assertEqual(prime, Decimal('800.00'))

    def test_12_ans_15_pct_de_6500(self):
        """6 500 × 15 % = 975 MAD."""
        prime = calculer_prime_anciennete(self.profil, Decimal('6500'), 12, self.param)
        self.assertEqual(prime, Decimal('975.00'))

    def test_20_ans_20_pct_de_12345(self):
        """12 345 × 20 % = 2 469 MAD."""
        prime = calculer_prime_anciennete(self.profil, Decimal('12345'), 20, self.param)
        self.assertEqual(prime, Decimal('2469.00'))

    def test_25_ans_25_pct_de_7777(self):
        """7 777 × 25 % = 1 944,25 MAD."""
        prime = calculer_prime_anciennete(self.profil, Decimal('7777'), 25, self.param)
        self.assertEqual(prime, Decimal('1944.25'))

    def test_zero_an_retourne_zero(self):
        """Ancienneté insuffisante → prime nulle."""
        prime = calculer_prime_anciennete(self.profil, Decimal('10000'), 0, self.param)
        self.assertEqual(prime, Decimal('0.00'))

    def test_1_an_retourne_zero(self):
        """1 an (< seuil 2 ans) → prime nulle."""
        prime = calculer_prime_anciennete(self.profil, Decimal('10000'), 1, self.param)
        self.assertEqual(prime, Decimal('0.00'))

    def test_arrondi_centime(self):
        """Résultat arrondi au centime."""
        prime = calculer_prime_anciennete(
            self.profil, Decimal('3111.39'), 2, self.param)
        # 3111.39 × 5 % = 155.5695 → arrondi à 155.57
        self.assertEqual(prime, Decimal('155.57'))


# ── calculer_bulletin — intégration ────────────────────────────────────────

class BulletinAncienneteTests(TestCase):
    """Intégration : la prime d'ancienneté s'intègre dans le bulletin."""

    def setUp(self):
        self.co = make_company('anc-bull')
        ensure_defaults(self.co)

    def _make_context(self, date_embauche, salaire=Decimal('10000'),
                      annee=2026, mois=6, matricule='B1'):
        dossier = make_dossier(self.co, matricule, date_embauche)
        profil = make_profil(self.co, dossier, salaire)
        periode = make_periode(self.co, annee, mois)
        return profil, periode

    def test_2_ans_anciennete_integree_dans_brut(self):
        """Exactement 2 ans d'ancienneté au 01/06/2026 → prime 5 % dans le brut."""
        profil, periode = self._make_context(
            date_embauche=date(2024, 6, 1), salaire=Decimal('10000'))
        res = calculer_bulletin(profil, periode)
        # Brut attendu = 10 000 (SB) + 500 (prime 5 %)
        self.assertEqual(res['brut'], Decimal('10500.00'))
        self.assertEqual(res['prime_anciennete'], Decimal('500.00'))

    def test_anciennete_ligne_dans_bulletin(self):
        """La ligne ANCIENNETE apparaît dans les lignes du bulletin."""
        profil, periode = self._make_context(
            date_embauche=date(2024, 6, 1), matricule='B2')
        res = calculer_bulletin(profil, periode)
        codes = [ligne['code'] for ligne in res['lignes']]
        self.assertIn('ANCIENNETE', codes)

    def test_sans_anciennete_suffisante_pas_de_prime(self):
        """Moins de 2 ans → prime 0, brut inchangé, pas de ligne ANCIENNETE."""
        profil, periode = self._make_context(
            date_embauche=date(2025, 1, 1),  # 1 an et 5 mois
            salaire=Decimal('10000'), matricule='B3')
        res = calculer_bulletin(profil, periode)
        self.assertEqual(res['prime_anciennete'], Decimal('0'))
        self.assertEqual(res['brut'], Decimal('10000.00'))
        codes = [ligne['code'] for ligne in res['lignes']]
        self.assertNotIn('ANCIENNETE', codes)

    def test_sans_date_embauche_pas_de_prime(self):
        """Date d'embauche non renseignée → prime 0."""
        profil, periode = self._make_context(
            date_embauche=None, salaire=Decimal('10000'), matricule='B4')
        res = calculer_bulletin(profil, periode)
        self.assertEqual(res['prime_anciennete'], Decimal('0'))

    def test_5_ans_10_pct(self):
        """5 ans d'ancienneté → prime 10 %."""
        profil, periode = self._make_context(
            date_embauche=date(2021, 6, 1), salaire=Decimal('8000'), matricule='B5')
        res = calculer_bulletin(profil, periode)
        self.assertEqual(res['prime_anciennete'], Decimal('800.00'))
        self.assertEqual(res['brut'], Decimal('8800.00'))

    def test_25_ans_25_pct(self):
        """25 ans d'ancienneté → prime 25 %."""
        profil, periode = self._make_context(
            date_embauche=date(2001, 6, 1), salaire=Decimal('6000'), matricule='B6')
        res = calculer_bulletin(profil, periode)
        self.assertEqual(res['prime_anciennete'], Decimal('1500.00'))
        self.assertEqual(res['brut'], Decimal('7500.00'))

    def test_prime_anciennete_augmente_net(self):
        """La prime d'ancienneté augmente le net à payer."""
        profil_sans, periode_sans = self._make_context(
            date_embauche=None, salaire=Decimal('10000'), matricule='B7')
        profil_avec, periode_avec = self._make_context(
            date_embauche=date(2021, 6, 1), salaire=Decimal('10000'), matricule='B8',
            mois=7)
        net_sans = calculer_bulletin(profil_sans, periode_sans)['net_a_payer']
        net_avec = calculer_bulletin(profil_avec, periode_avec)['net_a_payer']
        self.assertGreater(net_avec, net_sans)


# ── Personnalisation du barème ─────────────────────────────────────────────

class BaremeAnciennetePersonnaliseTests(TestCase):
    """Les taux/seuils d'ancienneté éditables sur ParametrePaie sont respectés."""

    def setUp(self):
        self.co = make_company('anc-custom')
        ensure_defaults(self.co)
        self.param = get_param(self.co)

    def test_seuil_personnalise_1_an(self):
        """Si le fondateur change le seuil 1 à 1 an, la prime s'applique dès 1 an."""
        self.param.anciennete_seuil_1 = 1
        self.param.anciennete_taux_1 = Decimal('3')
        self.param.save()
        self.assertEqual(taux_anciennete(self.param, 1), Decimal('3'))
        self.assertEqual(taux_anciennete(self.param, 0), Decimal('0'))

    def test_taux_personnalise_5_pct_a_8_pct(self):
        """Taux du seuil 2 changé de 10 % à 8 %."""
        self.param.anciennete_taux_2 = Decimal('8')
        self.param.save()
        self.assertEqual(taux_anciennete(self.param, 5), Decimal('8'))

    def test_seuil_et_taux_personnalises_dans_bulletin(self):
        """Le bulletin utilise le barème personnalisé."""
        self.param.anciennete_seuil_1 = 1
        self.param.anciennete_taux_1 = Decimal('3')
        self.param.save()
        dossier = make_dossier(self.co, 'C1', date_embauche=date(2025, 1, 1))
        profil = make_profil(self.co, dossier, Decimal('10000'))
        periode = make_periode(self.co, 2026, 6)
        res = calculer_bulletin(profil, periode)
        # 10 000 × 3 % = 300
        self.assertEqual(res['prime_anciennete'], Decimal('300.00'))


# ── Multi-tenant ───────────────────────────────────────────────────────────

class AncienneteIsolationTests(TestCase):
    """La prime de la société B n'affecte pas le bulletin de la société A."""

    def test_isolation_societes(self):
        co_a = make_company('anc-iso-a')
        co_b = make_company('anc-iso-b')
        ensure_defaults(co_a)
        ensure_defaults(co_b)

        # Société A : employé sans ancienneté suffisante.
        dos_a = make_dossier(co_a, 'IA1', date_embauche=date(2025, 6, 1))
        profil_a = make_profil(co_a, dos_a, Decimal('10000'))
        periode_a = make_periode(co_a, 2026, 6)

        # Société B : employé avec 10 ans d'ancienneté.
        dos_b = make_dossier(co_b, 'IB1', date_embauche=date(2016, 6, 1))
        profil_b = make_profil(co_b, dos_b, Decimal('10000'))
        periode_b = make_periode(co_b, 2026, 6)

        brut_a = calculer_bulletin(profil_a, periode_a)['brut']
        brut_b = calculer_bulletin(profil_b, periode_b)['brut']

        # A ne doit pas avoir de prime d'ancienneté.
        self.assertEqual(
            calculer_bulletin(profil_a, periode_a)['prime_anciennete'],
            Decimal('0'))
        # B doit avoir 10 % de prime.
        self.assertEqual(
            calculer_bulletin(profil_b, periode_b)['prime_anciennete'],
            Decimal('1000.00'))
        # Les bruts sont bien distincts.
        self.assertNotEqual(brut_a, brut_b)
