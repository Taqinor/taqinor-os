"""Tests ZPAI1 — Rapport d'analyse de paie (pivot rubrique/département × mois).

Odoo « Payroll Analysis » n'avait aucun équivalent. Couvre :
* ``analyse_paie`` agrège les ``LigneBulletin`` VALIDÉES sur une fenêtre
  multi-mois par code de rubrique, une colonne par mois ;
* le regroupement ``departement`` lit le département via
  ``rh.selectors.departements_par_employe`` (jamais ``rh.models``) ;
* les brouillons/périodes hors fenêtre sont exclus ; isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie import selectors as paie_selectors
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import ensure_defaults, generer_bulletin, valider_bulletin
from apps.rh.models import Departement, DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class AnalysePaieTests(TestCase):
    def setUp(self):
        self.co = make_company('zpai1')
        ensure_defaults(self.co)

    def _bulletin(self, annee, mois, mat, salaire=Decimal('10000'),
                  valider=True, departement=None):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=annee, mois=mois)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            departement=departement)
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, periode)
        if valider:
            valider_bulletin(b)
        return b

    def test_agregat_par_rubrique_sur_deux_mois(self):
        self._bulletin(2026, 5, 'A1')
        self._bulletin(2026, 6, 'A2')
        r = paie_selectors.analyse_paie(
            self.co, 2026, 5, 2026, 6, group_by='rubrique')
        self.assertEqual(r['mois'], ['2026-05', '2026-06'])
        self.assertGreater(len(r['lignes']), 0)
        for ligne in r['lignes']:
            total_recompute = sum(
                ligne['totaux_par_mois'].values(), Decimal('0.00'))
            self.assertEqual(ligne['total'], total_recompute)
        total_recompute_general = sum(
            (ligne['total'] for ligne in r['lignes']), Decimal('0.00'))
        self.assertEqual(r['total_general'], total_recompute_general)

    def test_brouillon_exclu(self):
        self._bulletin(2026, 6, 'B1', valider=False)
        r = paie_selectors.analyse_paie(self.co, 2026, 6, 2026, 6)
        self.assertEqual(r['total_general'], Decimal('0.00'))

    def test_hors_fenetre_exclu(self):
        self._bulletin(2026, 1, 'C1')
        r = paie_selectors.analyse_paie(self.co, 2026, 6, 2026, 6)
        self.assertEqual(r['total_general'], Decimal('0.00'))

    def test_group_by_departement(self):
        dep = Departement.objects.create(company=self.co, nom='Technique')
        self._bulletin(2026, 6, 'D1', departement=dep)
        r = paie_selectors.analyse_paie(
            self.co, 2026, 6, 2026, 6, group_by='departement')
        libelles = {ligne['libelle'] for ligne in r['lignes']}
        self.assertIn('Technique', libelles)

    def test_group_by_invalide_leve(self):
        with self.assertRaises(ValueError):
            paie_selectors.analyse_paie(
                self.co, 2026, 6, 2026, 6, group_by='autre_chose')

    def test_isolation_tenant(self):
        self._bulletin(2026, 6, 'T1')
        autre = make_company('zpai1-autre')
        ensure_defaults(autre)
        r = paie_selectors.analyse_paie(autre, 2026, 6, 2026, 6)
        self.assertEqual(r['total_general'], Decimal('0.00'))
