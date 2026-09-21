"""NTFPA6 — Verrouillage post-clôture : un cycle clos rend ses lignes de
budget immuables (ValidationError sur save()/delete()), même patron que
compta.EcritureComptable._verifier_periode_ouverte."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement


class TestVerrouillagePostCloture(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa6-co', defaults={'nom': 'NTFPA6 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='MKT', nom='Marketing')

    def test_creation_refusee_sur_cycle_clos(self):
        self.cycle.statut = CycleBudgetaire.Statut.CLOS
        self.cycle.save(update_fields=['statut'])
        with self.assertRaises(ValidationError):
            LigneBudgetDepartement.objects.create(
                company=self.company, cycle=self.cycle, departement=self.dept,
                categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('100'))

    def test_modification_refusee_apres_cloture(self):
        ligne = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=2, montant_prevu=Decimal('100'))
        self.cycle.statut = CycleBudgetaire.Statut.CLOS
        self.cycle.save(update_fields=['statut'])
        ligne.montant_prevu = Decimal('999')
        with self.assertRaises(ValidationError):
            ligne.save()

    def test_suppression_refusee_apres_cloture(self):
        ligne = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=3, montant_prevu=Decimal('100'))
        self.cycle.statut = CycleBudgetaire.Statut.CLOS
        self.cycle.save(update_fields=['statut'])
        with self.assertRaises(ValidationError):
            ligne.delete()
        self.assertTrue(
            LigneBudgetDepartement.objects.filter(pk=ligne.pk).exists())

    def test_ecriture_normale_sur_cycle_ouvert(self):
        self.cycle.statut = CycleBudgetaire.Statut.OUVERT_SAISIE
        self.cycle.save(update_fields=['statut'])
        ligne = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=4, montant_prevu=Decimal('100'))
        ligne.montant_prevu = Decimal('200')
        ligne.save()
        ligne.refresh_from_db()
        self.assertEqual(ligne.montant_prevu, Decimal('200'))
