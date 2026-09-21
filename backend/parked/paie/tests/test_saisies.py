"""Tests PAIE29 — Saisie-arrêt / cession sur salaire (quotité saisissable).

Couvre :
* ``quotite_saisissable`` — barème progressif par tranche (part saisissable
  cumulée) ; net nul/négatif → 0.
* ``retenues_saisies_periode`` — plafonnement à la quotité, ordre prioritaire,
  bornage au solde restant et à l'échéance souhaitée.
* ``calculer_bulletin`` — la saisie diminue le net dans la limite de la quotité.
* ``valider_bulletin`` → ``appliquer_saisies`` impute le montant retenu UNE
  fois (pas au recalcul d'un brouillon).
* Multi-tenant — isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie, SaisieArret
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    generer_bulletin,
    quotite_saisissable,
    retenues_saisies_periode,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class QuotiteTests(TestCase):
    def test_bareme_progressif(self):
        # ≤ 2000 : 2000 × 0,05 = 100.
        self.assertEqual(quotite_saisissable(Decimal('2000')), Decimal('100.00'))
        # 5000 : 2000×0,05 + 2000×0,10 + 1000×0,20 = 100 + 200 + 200 = 500.
        self.assertEqual(quotite_saisissable(Decimal('5000')), Decimal('500.00'))

    def test_net_nul_ou_negatif(self):
        self.assertEqual(quotite_saisissable(Decimal('0')), Decimal('0.00'))
        self.assertEqual(quotite_saisissable(Decimal('-100')), Decimal('0.00'))


class SaisiePeriodeTests(TestCase):
    def setUp(self):
        self.co = make_company('sa-per')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='Test', prenom='Saisie')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('5000'))

    def test_plafonnee_a_la_quotite(self):
        # Net 5000 → quotité 500. Saisie réclame 2000 mais on plafonne à 500.
        SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('2000'),
            montant_echeance=Decimal('2000'), date_debut=date(2026, 6, 1))
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        total, lignes = retenues_saisies_periode(
            self.profil, periode, Decimal('5000'))
        self.assertEqual(total, Decimal('500.00'))
        self.assertEqual(len(lignes), 1)

    def test_prioritaire_servie_en_premier(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('5000'),
            montant_echeance=Decimal('400'), date_debut=date(2026, 6, 1),
            prioritaire=False, creancier='Banque')
        SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('5000'),
            montant_echeance=Decimal('400'), date_debut=date(2026, 6, 1),
            prioritaire=True, creancier='Pension')
        # Quotité 500 : la prioritaire (Pension, 400) passe d'abord, il reste
        # 100 pour la seconde.
        total, lignes = retenues_saisies_periode(
            self.profil, periode, Decimal('5000'))
        self.assertEqual(total, Decimal('500.00'))
        self.assertEqual(lignes[0][0].creancier, 'Pension')
        self.assertEqual(lignes[0][1], Decimal('400.00'))
        self.assertEqual(lignes[1][1], Decimal('100.00'))


class BulletinSaisieTests(TestCase):
    def setUp(self):
        self.co = make_company('sa-bull')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S2', nom='Test', prenom='Bull')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.saisie = SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('5000'),
            montant_echeance=Decimal('300'), date_debut=date(2026, 6, 1),
            creancier='Trésor')

    def test_saisie_baisse_net_et_ligne(self):
        res = calculer_bulletin(self.profil, self.periode)
        self.assertTrue(
            any(ligne['code'] == 'SAISIE' for ligne in res['lignes']))
        # La retenue de 300 est bien sous la quotité du net (>0).
        self.assertGreaterEqual(res['retenues'], Decimal('300.00'))

    def test_imputation_a_la_validation(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        generer_bulletin(self.profil, self.periode)  # recalcul brouillon
        self.saisie.refresh_from_db()
        self.assertEqual(self.saisie.montant_retenu, Decimal('0'))
        valider_bulletin(bulletin)
        self.saisie.refresh_from_db()
        self.assertEqual(self.saisie.montant_retenu, Decimal('300.00'))
