"""Tests PAIE26 — Paiement & décompte des congés/absences sur le bulletin.

Couvre :
* Absence NON rémunérée (sans solde) : décomptée du salaire de base proraté
  ET portée en retenue (comportement historique conservé).
* Absence RÉMUNÉRÉE (congé payé) : ni déduite de la proration, ni portée en
  retenue → le salarié est payé comme présent.
* ``calculer_salaire_base_periode`` ignore les jours d'absence rémunérée.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_bulletin,
    calculer_salaire_base_periode,
    ensure_defaults,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_setup(slug):
    co = make_company(slug)
    ensure_defaults(co)
    dossier = DossierEmploye.objects.create(
        company=co, matricule='A1', nom='Test', prenom='Abs')
    profil = ProfilPaie.objects.create(
        company=co, employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=Decimal('2600'),  # 100/jour sur 26 jours
        jours_travail_mensuel=26, affilie_cnss=True, affilie_amo=True)
    periode = PeriodePaie.objects.create(company=co, annee=2026, mois=6)
    return co, profil, periode


class AbsenceNonRemunereeTests(TestCase):
    def setUp(self):
        self.co, self.profil, self.periode = make_setup('abs-nr')

    def test_decompte_proration_et_retenue(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('2'),
            montant=Decimal('200'), remunere=False)
        # Proration : 2600 × (26−2)/26 = 2400.
        base = calculer_salaire_base_periode(
            self.profil, self.periode)
        self.assertEqual(base, Decimal('2400.00'))
        res = calculer_bulletin(self.profil, self.periode)
        # La retenue de 200 figure dans les retenues variables.
        self.assertEqual(res['retenues'], Decimal('200.00'))


class AbsenceRemunereeTests(TestCase):
    def setUp(self):
        self.co, self.profil, self.periode = make_setup('abs-rem')

    def test_payee_comme_presente(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('3'),
            montant=Decimal('300'), remunere=True, deduit_solde=True)
        # Aucune déduction de proration.
        base = calculer_salaire_base_periode(self.profil, self.periode)
        self.assertEqual(base, Decimal('2600.00'))
        res = calculer_bulletin(self.profil, self.periode)
        # Aucune retenue.
        self.assertEqual(res['retenues'], Decimal('0.00'))
        self.assertEqual(res['brut'], Decimal('2600.00'))
        # Pas de ligne retenue pour l'absence rémunérée.
        retenues = [
            ligne for ligne in res['lignes']
            if ligne['type'] == 'retenue']
        self.assertEqual(retenues, [])
