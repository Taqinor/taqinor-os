"""Tests ZPAI3 — Rapport « Coût employeur » consolidé de la période.

Odoo a un rapport dédié totalisant le coût employeur. Couvre :
* le total = brut + charges patronales + provisions de tous les bulletins
  validés de la période ;
* le ratio coût/net et le coût moyen par tête sont corrects ;
* une rubrique patronale itemisée (``ALLOC_FAM``) dé-flaggée
  (``apparait_cout_employeur=False``) sort de l'agrégat ;
* aucun bulletin validé -> zéros propres (jamais de division par zéro) ;
* isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie, Rubrique
from apps.paie.services import (
    cout_employeur, ensure_defaults, generer_bulletin, valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class CoutEmployeurTests(TestCase):
    def setUp(self):
        self.co = make_company('zpai3')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin(self, mat, salaire=Decimal('10000'), valider=True):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        if valider:
            valider_bulletin(b)
        return b

    def test_total_employeur_egale_brut_plus_patronales_plus_provisions(self):
        b1 = self._bulletin('A1')
        b2 = self._bulletin('A2', salaire=Decimal('15000'))
        r = cout_employeur(self.periode)
        self.assertEqual(r['nombre_salaries'], 2)
        self.assertEqual(r['total_brut'], b1.brut + b2.brut)
        self.assertEqual(
            r['total_charges_patronales'],
            b1.charges_patronales + b2.charges_patronales)
        self.assertEqual(
            r['total_provisions'], b1.provision_conges + b2.provision_conges)
        self.assertEqual(
            r['total_employeur'],
            r['total_brut'] + r['total_charges_patronales']
            + r['total_provisions'])

    def test_ratio_et_moyenne_par_tete(self):
        self._bulletin('B1')
        self._bulletin('B2', salaire=Decimal('20000'))
        r = cout_employeur(self.periode)
        self.assertEqual(
            r['ratio_cout_net'], r['total_employeur'] / r['total_net'])
        self.assertEqual(
            r['cout_moyen_par_tete'], r['total_employeur'] / 2)

    def test_brouillon_exclu(self):
        self._bulletin('C1', valider=False)
        r = cout_employeur(self.periode)
        self.assertEqual(r['nombre_salaries'], 0)

    def test_sans_bulletin_valide_zero_propre(self):
        r = cout_employeur(self.periode)
        self.assertEqual(r['nombre_salaries'], 0)
        self.assertEqual(r['total_employeur'], Decimal('0.00'))
        self.assertIsNone(r['ratio_cout_net'])
        self.assertEqual(r['cout_moyen_par_tete'], Decimal('0.00'))

    def test_rubrique_deflaggee_sort_de_lagregat(self):
        self._bulletin('D1')
        r_avant = cout_employeur(self.periode)

        Rubrique.objects.create(
            company=self.co, code='ALLOC_FAM', libelle='Allocations',
            type=Rubrique.TYPE_COTISATION, apparait_cout_employeur=False)
        r_apres = cout_employeur(self.periode)

        self.assertLess(r_apres['total_employeur'], r_avant['total_employeur'])
        self.assertIn('ALLOC_FAM', r_apres['rubriques_exclues'])

    def test_isolation_tenant(self):
        self._bulletin('T1')
        autre = make_company('zpai3-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        r = cout_employeur(periode_autre)
        self.assertEqual(r['nombre_salaries'], 0)
