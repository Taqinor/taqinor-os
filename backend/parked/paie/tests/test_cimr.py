"""Tests PAIE20 — Cotisation CIMR OPTIONNELLE (taux par employé adhérent).

La CIMR (retraite complémentaire) est FACULTATIVE : seuls les employés
ADHÉRENTS cotisent, et chacun avec SON propre taux porté par le
``ProfilPaie`` (``affilie_cimr`` / ``taux_cimr_salarial``).

Couvre :
* ``cimr_salariale`` (helper) — adhérent → ``brut × taux / 100`` ;
  non adhérent → 0 (défaut « pas d'adhésion → pas de CIMR ») ; taux nul → 0 ;
  assiette NON plafonnée (sur le brut intégral).
* ``calculer_bulletin`` — intégration : un profil non adhérent n'a aucune CIMR
  (défaut), un adhérent voit SA cotisation calculée avec SON taux, et la CIMR
  réduit bien le net à payer & le net imposable.
* Per-employee : deux adhérents de la MÊME société avec des taux différents
  obtiennent des cotisations différentes.
* Multi-tenant — chaque profil porte son propre taux, scopé société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie
from apps.paie.services import (
    calculer_bulletin,
    cimr_salariale,
    ensure_defaults,
)
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


# ── Helper unitaire : cimr_salariale ───────────────────────────────────────

class CimrHelperTests(TestCase):
    """PAIE20 — ``cimr_salariale`` : optionnelle, par taux d'employé adhérent."""

    def test_adherent_calcule_sur_brut_integral(self):
        # Adhérent à 6 % sur un brut de 10000, assiette NON plafonnée.
        self.assertEqual(
            cimr_salariale(Decimal('10000'), affilie=True, taux=Decimal('6')),
            Decimal('600.00'))

    def test_non_adherent_zero_par_defaut(self):
        # Défaut : non adhérent → 0 même si un taux traîne.
        self.assertEqual(
            cimr_salariale(Decimal('10000')),
            Decimal('0.00'))
        self.assertEqual(
            cimr_salariale(Decimal('10000'), affilie=False, taux=Decimal('6')),
            Decimal('0.00'))

    def test_taux_nul_zero(self):
        # Adhérent mais taux nul → 0.
        self.assertEqual(
            cimr_salariale(Decimal('10000'), affilie=True, taux=Decimal('0')),
            Decimal('0.00'))

    def test_taux_par_employe(self):
        # Le taux est propre à l'employé : 3 % vs 6 % → cotisations distinctes.
        self.assertEqual(
            cimr_salariale(Decimal('8000'), affilie=True, taux=Decimal('3')),
            Decimal('240.00'))
        self.assertEqual(
            cimr_salariale(Decimal('8000'), affilie=True, taux=Decimal('6')),
            Decimal('480.00'))


# ── Intégration : calculer_bulletin ────────────────────────────────────────

class CimrBulletinTests(TestCase):
    """Le bulletin n'applique la CIMR qu'aux profils adhérents, à leur taux."""

    def setUp(self):
        self.co = make_company('cimr-bull')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_non_adherent_aucune_cimr(self):
        # make_profil ne pose pas affilie_cimr → défaut False (non adhérent).
        dossier = make_dossier(self.co, 'NAD')
        profil = make_profil(self.co, dossier, Decimal('10000'))
        self.assertFalse(profil.affilie_cimr)  # opt-in : défaut non adhérent
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['cimr_salariale'], Decimal('0.00'))

    def test_adherent_cotise_a_son_taux(self):
        dossier = make_dossier(self.co, 'ADH')
        profil = make_profil(self.co, dossier, Decimal('10000'))
        profil.affilie_cimr = True
        profil.taux_cimr_salarial = Decimal('6')
        profil.save()
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['cimr_salariale'], Decimal('600.00'))  # 10000 × 6 %

    def test_cimr_reduit_net_a_payer_et_imposable(self):
        """Activer la CIMR baisse le net à payer (et le net imposable)."""
        dossier_off = make_dossier(self.co, 'OFF')
        profil_off = make_profil(self.co, dossier_off, Decimal('10000'))
        res_off = calculer_bulletin(profil_off, self.periode)

        dossier_on = make_dossier(self.co, 'ON')
        profil_on = make_profil(self.co, dossier_on, Decimal('10000'))
        profil_on.affilie_cimr = True
        profil_on.taux_cimr_salarial = Decimal('6')
        profil_on.save()
        res_on = calculer_bulletin(profil_on, self.periode)

        self.assertEqual(res_on['cimr_salariale'], Decimal('600.00'))
        self.assertLess(res_on['net_a_payer'], res_off['net_a_payer'])
        self.assertLess(res_on['net_imposable'], res_off['net_imposable'])

    def test_taux_par_employe_meme_societe(self):
        """Deux adhérents de la même société, taux différents → cotisations différentes."""
        d_a = make_dossier(self.co, 'PA')
        p_a = make_profil(self.co, d_a, Decimal('10000'))
        p_a.affilie_cimr = True
        p_a.taux_cimr_salarial = Decimal('3')
        p_a.save()

        d_b = make_dossier(self.co, 'PB')
        p_b = make_profil(self.co, d_b, Decimal('10000'))
        p_b.affilie_cimr = True
        p_b.taux_cimr_salarial = Decimal('6')
        p_b.save()

        res_a = calculer_bulletin(p_a, self.periode)
        res_b = calculer_bulletin(p_b, self.periode)
        self.assertEqual(res_a['cimr_salariale'], Decimal('300.00'))
        self.assertEqual(res_b['cimr_salariale'], Decimal('600.00'))


# ── Multi-tenant : le taux est porté par le profil, scopé société ──────────

class CimrIsolationTests(TestCase):
    """Le taux CIMR est propre à chaque profil — aucune fuite inter-société."""

    def test_taux_porte_par_le_profil_scope_societe(self):
        co_a = make_company('cimr-iso-a')
        co_b = make_company('cimr-iso-b')
        ensure_defaults(co_a)
        ensure_defaults(co_b)

        d_a = make_dossier(co_a, 'IA')
        p_a = make_profil(co_a, d_a, Decimal('10000'))
        p_a.affilie_cimr = True
        p_a.taux_cimr_salarial = Decimal('4')
        p_a.save()

        d_b = make_dossier(co_b, 'IB')
        p_b = make_profil(co_b, d_b, Decimal('10000'))
        p_b.affilie_cimr = True
        p_b.taux_cimr_salarial = Decimal('6')
        p_b.save()

        per_a = PeriodePaie.objects.create(company=co_a, annee=2026, mois=6)
        per_b = PeriodePaie.objects.create(company=co_b, annee=2026, mois=6)

        # Chaque société/profil applique SON propre taux ; aucune influence croisée.
        self.assertEqual(
            calculer_bulletin(p_a, per_a)['cimr_salariale'], Decimal('400.00'))
        self.assertEqual(
            calculer_bulletin(p_b, per_b)['cimr_salariale'], Decimal('600.00'))
        # Le profil de A reste à 4 % indépendamment de B.
        self.assertEqual(p_a.taux_cimr_salarial, Decimal('4'))
        self.assertEqual(p_b.taux_cimr_salarial, Decimal('6'))
