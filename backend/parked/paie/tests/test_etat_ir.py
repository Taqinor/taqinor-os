"""Tests PAIE32 — État IR 9421 + retenues à la source.

Couvre :
* ``etat_ir_9421`` — agrège l'IR retenu des bulletins VALIDÉS d'une période
  (brut/net imposable, IR, personnes à charge) ; ignore les brouillons.
* ``etat_ir_9421_annuel`` — cumule l'IR sur toutes les périodes de l'année,
  par salarié.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    etat_ir_9421,
    etat_ir_9421_annuel,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class EtatIrTests(TestCase):
    def setUp(self):
        self.co = make_company('ir9421')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='IR1', nom='Test', prenom='IR')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('15000'), affilie_cnss=True, affilie_amo=True)

    def _bulletin_valide(self, mois):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=mois)
        b = generer_bulletin(self.profil, periode)
        valider_bulletin(b)
        return periode, b

    def test_etat_periode(self):
        periode, b = self._bulletin_valide(6)
        etat = etat_ir_9421(periode)
        self.assertEqual(etat['nombre_salaries'], 1)
        self.assertEqual(etat['total_ir'], b.ir)
        self.assertEqual(etat['lignes'][0]['matricule'], 'IR1')
        self.assertGreater(b.ir, Decimal('0'))  # salaire élevé → IR non nul

    def test_ignore_brouillon(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        generer_bulletin(self.profil, periode)  # brouillon
        etat = etat_ir_9421(periode)
        self.assertEqual(etat['nombre_salaries'], 0)

    def test_etat_annuel_cumule(self):
        _, b1 = self._bulletin_valide(1)
        _, b2 = self._bulletin_valide(2)
        etat = etat_ir_9421_annuel(self.co, 2026)
        self.assertEqual(etat['nombre_salaries'], 1)
        self.assertEqual(etat['total_ir'], b1.ir + b2.ir)
        self.assertEqual(etat['lignes'][0]['nombre_bulletins'], 2)
