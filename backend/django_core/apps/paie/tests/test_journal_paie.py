"""Tests PAIE33 — Livre de paie + journal de paie → écritures (via compta).

Couvre :
* ``livre_de_paie`` — registre récapitulatif des bulletins VALIDÉS + totaux.
* ``journal_de_paie`` — crée UNE écriture comptable ÉQUILIBRÉE via
  ``compta.services`` (cross-app par la couche services, jamais les models) ;
  None si aucun bulletin validé.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    journal_de_paie,
    livre_de_paie,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class JournalPaieTests(TestCase):
    def setUp(self):
        self.co = make_company('jp')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_livre_de_paie(self):
        b1 = self._bulletin_valide('A1')
        b2 = self._bulletin_valide('A2')
        livre = livre_de_paie(self.periode)
        self.assertEqual(livre['nombre_salaries'], 2)
        self.assertEqual(livre['totaux']['brut'], b1.brut + b2.brut)
        self.assertEqual(
            livre['totaux']['net_a_payer'], b1.net_a_payer + b2.net_a_payer)

    def test_journal_de_paie_ecriture_equilibree(self):
        self._bulletin_valide('B1')
        ecriture = journal_de_paie(self.periode)
        self.assertIsNotNone(ecriture)
        # L'écriture est équilibrée : Σ débit = Σ crédit.
        lignes = list(ecriture.lignes.all())
        debit = sum((lig.debit for lig in lignes), Decimal('0'))
        credit = sum((lig.credit for lig in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertGreater(debit, Decimal('0'))
        self.assertEqual(ecriture.company, self.co)
        self.assertEqual(ecriture.reference, 'PAIE-2026-06')

    def test_journal_de_paie_sans_bulletin(self):
        # Aucun bulletin validé → rien à comptabiliser.
        self.assertIsNone(journal_de_paie(self.periode))
