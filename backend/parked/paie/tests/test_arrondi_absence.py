"""Tests ZPAI8 — Règles d'arrondi des jours/heures par type d'absence.

Couvre :
* ``_arrondir_jours_absence`` — ``aucun`` (défaut, y compris sans rubrique)
  laisse la quantité inchangée ; ``journee``/``sup`` arrondit au jour
  supérieur ; ``demi_journee``/``sup`` au demi-jour supérieur ;
  ``journee``/``inf`` au jour inférieur.
* ``calculer_salaire_base_periode`` applique la règle de la rubrique
  rattachée à l'élément d'absence, sur la proration mensuelle.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie, Rubrique
from apps.paie.services import (
    _arrondir_jours_absence,
    calculer_salaire_base_periode,
    ensure_defaults,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ArrondiHelperTests(TestCase):
    def setUp(self):
        self.co = make_company('arr-helper')

    def test_sans_rubrique_inchange(self):
        self.assertEqual(
            _arrondir_jours_absence(Decimal('1.3'), None), Decimal('1.3'))

    def test_rubrique_arrondi_aucun_inchange(self):
        rub = Rubrique.objects.create(
            company=self.co, code='ABS-AUCUN', libelle='Absence',
            arrondi=Rubrique.ARRONDI_AUCUN)
        self.assertEqual(
            _arrondir_jours_absence(Decimal('1.3'), rub), Decimal('1.3'))

    def test_journee_sup(self):
        rub = Rubrique.objects.create(
            company=self.co, code='ABS-J-SUP', libelle='Absence',
            arrondi=Rubrique.ARRONDI_JOURNEE, sens_arrondi=Rubrique.SENS_SUP)
        self.assertEqual(
            _arrondir_jours_absence(Decimal('1.3'), rub), Decimal('2'))

    def test_journee_inf(self):
        rub = Rubrique.objects.create(
            company=self.co, code='ABS-J-INF', libelle='Absence',
            arrondi=Rubrique.ARRONDI_JOURNEE, sens_arrondi=Rubrique.SENS_INF)
        self.assertEqual(
            _arrondir_jours_absence(Decimal('1.8'), rub), Decimal('1'))

    def test_demi_journee_sup(self):
        rub = Rubrique.objects.create(
            company=self.co, code='ABS-D-SUP', libelle='Absence',
            arrondi=Rubrique.ARRONDI_DEMI_JOURNEE,
            sens_arrondi=Rubrique.SENS_SUP)
        self.assertEqual(
            _arrondir_jours_absence(Decimal('1.1'), rub), Decimal('1.5'))

    def test_valeur_deja_ronde_inchangee(self):
        rub = Rubrique.objects.create(
            company=self.co, code='ABS-D-SUP2', libelle='Absence',
            arrondi=Rubrique.ARRONDI_DEMI_JOURNEE,
            sens_arrondi=Rubrique.SENS_SUP)
        self.assertEqual(
            _arrondir_jours_absence(Decimal('2.0'), rub), Decimal('2'))


class ProrationAvecArrondiTests(TestCase):
    def setUp(self):
        self.co = make_company('arr-proration')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='ARR1', nom='Test', prenom='Arrondi')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('2600'), jours_travail_mensuel=26,
            affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_arrondi_journee_sup_impacte_proration(self):
        rubrique = Rubrique.objects.create(
            company=self.co, code='ABS-STD', libelle='Absence standard',
            type=Rubrique.TYPE_RETENUE, arrondi=Rubrique.ARRONDI_JOURNEE,
            sens_arrondi=Rubrique.SENS_SUP)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('1.3'),
            rubrique=rubrique, remunere=False)
        # 1,3 jour arrondi à 2 jours (journée sup) : 2600 × (26−2)/26 = 2400.
        base = calculer_salaire_base_periode(self.profil, self.periode)
        self.assertEqual(base, Decimal('2400.00'))

    def test_sans_rubrique_comportement_actuel(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('1.3'),
            remunere=False)
        # Sans rubrique : quantité brute, non arrondie.
        # 2600 × (26−1.3)/26 = 2470.
        base = calculer_salaire_base_periode(self.profil, self.periode)
        self.assertEqual(base, Decimal('2470.00'))
