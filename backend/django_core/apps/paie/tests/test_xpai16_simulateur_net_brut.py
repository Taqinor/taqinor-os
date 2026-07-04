"""Tests XPAI16 — Simulateur de bulletin + calcul net→brut.

Couvre : ``simuler_bulletin`` ne crée AUCUNE ligne en base (what-if pur) ;
``brut_pour_net_cible`` converge au centime sur 3 cas (SMIG, cadre, avec
CIMR) ; round-trip brut->net->brut cohérent.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import BulletinPaie, ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import (
    bareme_en_vigueur,
    brut_pour_net_cible,
    ensure_defaults,
    parametre_en_vigueur,
    simuler_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class SimulerBulletinTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai16-sim')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='NomS1', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)

    def test_simulation_ne_cree_aucune_ligne(self):
        avant_bulletins = BulletinPaie.objects.count()
        avant_elements = ElementVariable.objects.count()
        simuler_bulletin(
            self.profil, self.periode, salaire=Decimal('15000'),
            prime=Decimal('2000'))
        self.assertEqual(BulletinPaie.objects.count(), avant_bulletins)
        self.assertEqual(ElementVariable.objects.count(), avant_elements)

    def test_salaire_par_defaut_est_reel(self):
        resultat = simuler_bulletin(self.profil, self.periode)
        self.assertEqual(resultat['salaire_simule'], Decimal('10000.00'))
        self.assertEqual(resultat['brut'], Decimal('10000.00'))

    def test_salaire_hypothetique_et_prime(self):
        resultat = simuler_bulletin(
            self.profil, self.periode, salaire=Decimal('12000'),
            prime=Decimal('1000'))
        self.assertEqual(resultat['brut'], Decimal('13000.00'))
        self.assertGreater(resultat['net_a_payer'], Decimal('0'))
        self.assertLess(resultat['net_a_payer'], resultat['brut'])

    def test_personnes_a_charge_reduit_ir(self):
        sans_pac = simuler_bulletin(
            self.profil, self.periode, salaire=Decimal('15000'),
            personnes_a_charge=0)
        avec_pac = simuler_bulletin(
            self.profil, self.periode, salaire=Decimal('15000'),
            personnes_a_charge=4)
        self.assertLessEqual(avec_pac['ir'], sans_pac['ir'])


class BrutPourNetCibleTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai16-inverse')
        ensure_defaults(self.co)
        le_jour = None
        from datetime import date
        le_jour = date(2026, 1, 1)
        self.parametre = parametre_en_vigueur(self.co, le_jour)
        self.bareme = bareme_en_vigueur(self.co, le_jour)

    def _converge(self, net_cible, **kwargs):
        resultat = brut_pour_net_cible(
            net_cible, parametre=self.parametre, bareme=self.bareme,
            **kwargs)
        self.assertAlmostEqual(
            float(resultat['net_a_payer']), float(net_cible), delta=0.02)
        return resultat

    def test_converge_smig(self):
        # SMIG ≈ 3111 MAD net mensuel (ordre de grandeur).
        self._converge(Decimal('3000'))

    def test_converge_cadre(self):
        # Cadre : net cible élevé, tranches IR hautes.
        self._converge(Decimal('15000'), personnes_a_charge=2)

    def test_converge_avec_cimr(self):
        self._converge(
            Decimal('9000'), affilie_cimr=True, taux_cimr=Decimal('6'))

    def test_net_cible_zero_ou_negatif_leve(self):
        with self.assertRaises(ValueError):
            brut_pour_net_cible(
                Decimal('0'), parametre=self.parametre, bareme=self.bareme)
        with self.assertRaises(ValueError):
            brut_pour_net_cible(
                Decimal('-100'), parametre=self.parametre,
                bareme=self.bareme)

    def test_round_trip_brut_net_brut(self):
        # brut connu -> net simulé -> brut retrouvé (cohérence du solveur).
        from apps.paie.services import _simuler_montant_net

        brut_connu = Decimal('12000')
        intermediaire = _simuler_montant_net(
            brut_connu, parametre=self.parametre, bareme=self.bareme)
        net_cible = intermediaire['net_a_payer']
        resultat = brut_pour_net_cible(
            net_cible, parametre=self.parametre, bareme=self.bareme)
        self.assertAlmostEqual(
            float(resultat['brut']), float(brut_connu), delta=1.0)
