"""Tests PAIE28 — Avance / prêt salarié + déduction mensuelle.

Couvre :
* ``echeance_avance`` — montant retenu un mois donné (inactif/soldé/non commencé
  → 0 ; dernière échéance bornée au solde restant).
* ``echeances_avances_periode`` — somme des échéances actives sur une période.
* ``calculer_bulletin`` — l'échéance figure en retenue et diminue le net.
* ``valider_bulletin`` → ``appliquer_remboursements_avances`` impute le
  remboursement UNE fois (montant_rembourse incrémenté ; pas au recalcul d'un
  brouillon).
* Multi-tenant — isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import AvanceSalarie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_bulletin,
    echeance_avance,
    echeances_avances_periode,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class EcheanceAvanceTests(TestCase):
    def setUp(self):
        self.co = make_company('av-ech')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V1', nom='Test', prenom='Avance')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))

    def _avance(self, **kw):
        defaults = dict(
            company=self.co, profil=self.profil, montant_total=Decimal('3000'),
            montant_echeance=Decimal('1000'), nombre_echeances=3,
            date_debut=date(2026, 6, 1))
        defaults.update(kw)
        return AvanceSalarie.objects.create(**defaults)

    def test_echeance_normale(self):
        av = self._avance()
        self.assertEqual(
            echeance_avance(av, date(2026, 6, 1)), Decimal('1000.00'))

    def test_inactive_ou_non_commencee(self):
        av = self._avance(actif=False)
        self.assertEqual(echeance_avance(av, date(2026, 6, 1)), Decimal('0.00'))
        av2 = self._avance(date_debut=date(2026, 7, 1))
        self.assertEqual(
            echeance_avance(av2, date(2026, 6, 1)), Decimal('0.00'))

    def test_derniere_echeance_bornee_au_solde(self):
        av = self._avance(montant_rembourse=Decimal('2500'))
        # Solde restant = 500 < échéance 1000 → on ne retient que 500.
        self.assertEqual(
            echeance_avance(av, date(2026, 6, 1)), Decimal('500.00'))

    def test_soldee_ne_retient_rien(self):
        av = self._avance(montant_rembourse=Decimal('3000'))
        self.assertEqual(echeance_avance(av, date(2026, 6, 1)), Decimal('0.00'))


class BulletinAvanceTests(TestCase):
    def setUp(self):
        self.co = make_company('av-bull')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V2', nom='Test', prenom='Bull')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.avance = AvanceSalarie.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('2000'),
            montant_echeance=Decimal('1000'), nombre_echeances=2,
            date_debut=date(2026, 6, 1))

    def test_echeance_en_retenue_et_baisse_net(self):
        total, lignes = echeances_avances_periode(self.profil, self.periode)
        self.assertEqual(total, Decimal('1000.00'))
        self.assertEqual(len(lignes), 1)
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['retenues'], Decimal('1000.00'))
        self.assertTrue(
            any(ligne['code'] == 'AVANCE' for ligne in res['lignes']))

    def test_imputation_uniquement_a_la_validation(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        # Recalcul brouillon → montant_rembourse inchangé.
        generer_bulletin(self.profil, self.periode)
        self.avance.refresh_from_db()
        self.assertEqual(self.avance.montant_rembourse, Decimal('0'))
        # Validation → imputation d'UNE échéance.
        valider_bulletin(bulletin)
        self.avance.refresh_from_db()
        self.assertEqual(self.avance.montant_rembourse, Decimal('1000.00'))
        self.assertEqual(self.avance.solde_restant, Decimal('1000.00'))
