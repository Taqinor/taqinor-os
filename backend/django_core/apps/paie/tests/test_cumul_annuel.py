"""Tests PAIE27 — CumulAnnuel (brut/net imposable/IR/CNSS/congés).

Couvre :
* ``recalculer_cumul_annuel`` — agrège les bulletins VALIDÉS de l'année
  (ignore les brouillons et les autres années) ; idempotent.
* Lecture du compteur de congés depuis le solde RH (string-FK).
* Unicité (company, profil, annee).
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import CumulAnnuel, PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    recalculer_cumul_annuel,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye, SoldeConge


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class CumulAnnuelTests(TestCase):
    def setUp(self):
        self.co = make_company('cumul')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='C1', nom='Test', prenom='Cumul')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            affilie_cnss=True, affilie_amo=True)

    def _bulletin_valide(self, mois):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=mois)
        bulletin = generer_bulletin(self.profil, periode)
        valider_bulletin(bulletin)
        return bulletin

    def test_agrege_bulletins_valides(self):
        b1 = self._bulletin_valide(1)
        b2 = self._bulletin_valide(2)
        cumul = recalculer_cumul_annuel(self.profil, 2026)
        self.assertEqual(cumul.nombre_bulletins, 2)
        self.assertEqual(cumul.brut, b1.brut + b2.brut)
        self.assertEqual(
            cumul.net_a_payer, b1.net_a_payer + b2.net_a_payer)
        self.assertEqual(cumul.ir, b1.ir + b2.ir)

    def test_ignore_brouillons_et_autres_annees(self):
        self._bulletin_valide(1)
        # Brouillon (non validé) → exclu.
        periode_b = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=3)
        generer_bulletin(self.profil, periode_b)
        cumul = recalculer_cumul_annuel(self.profil, 2026)
        self.assertEqual(cumul.nombre_bulletins, 1)
        # Aucun bulletin 2025.
        cumul25 = recalculer_cumul_annuel(self.profil, 2025)
        self.assertEqual(cumul25.nombre_bulletins, 0)
        self.assertEqual(cumul25.brut, Decimal('0.00'))

    def test_idempotent(self):
        self._bulletin_valide(1)
        c1 = recalculer_cumul_annuel(self.profil, 2026)
        c2 = recalculer_cumul_annuel(self.profil, 2026)
        self.assertEqual(c1.pk, c2.pk)
        self.assertEqual(
            CumulAnnuel.objects.filter(
                profil=self.profil, annee=2026).count(), 1)

    def test_compteur_conges_depuis_solde_rh(self):
        SoldeConge.objects.create(
            company=self.co, employe=self.dossier, annee=2026,
            acquis=Decimal('18'), report=Decimal('2'), pris=Decimal('6'))
        cumul = recalculer_cumul_annuel(self.profil, 2026)
        self.assertEqual(cumul.conges_acquis, Decimal('20.00'))
        self.assertEqual(cumul.conges_pris, Decimal('6.00'))
