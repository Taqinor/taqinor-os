"""NTFPA5 — Workflow soumission/validation d'un budget de département : un
budget rejeté repasse en saisie avec le motif visible au responsable."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
    SoumissionBudgetDepartement,
)
from apps.fpa.services import (
    rejeter_budget_departement, soumettre_budget_departement,
    valider_budget_departement,
)

User = get_user_model()


class TestWorkflowSoumissionValidation(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa5-co', defaults={'nom': 'NTFPA5 Co'})
        self.resp = User.objects.create_user(
            username='ntfpa5-resp', password='x', company=self.company)
        self.fpa = User.objects.create_user(
            username='ntfpa5-fpa', password='x', company=self.company,
            is_superuser=True)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31),
            statut=CycleBudgetaire.Statut.OUVERT_SAISIE)
        self.dept = Departement.objects.create(
            company=self.company, code='MKT', nom='Marketing', responsable=self.resp)
        self.ligne = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('1000'))

    def test_soumission_verrouille_edition(self):
        soumettre_budget_departement(self.company, self.cycle, self.dept, self.resp)
        self.ligne.montant_prevu = Decimal('2000')
        with self.assertRaises(ValidationError):
            self.ligne.save()

    def test_rejet_repasse_en_saisie_et_debloque_edition(self):
        soumettre_budget_departement(self.company, self.cycle, self.dept, self.resp)
        soumission = rejeter_budget_departement(
            self.company, self.cycle, self.dept, self.fpa, motif='Trop élevé')
        self.assertEqual(soumission.statut, SoumissionBudgetDepartement.Statut.REJETE)
        self.assertEqual(soumission.motif_rejet, 'Trop élevé')
        # L'édition redevient possible.
        self.ligne.montant_prevu = Decimal('500')
        self.ligne.save()
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.montant_prevu, Decimal('500'))

    def test_validation_ne_peut_suivre_que_soumis(self):
        with self.assertRaises(ValidationError):
            valider_budget_departement(self.company, self.cycle, self.dept, self.fpa)
        soumettre_budget_departement(self.company, self.cycle, self.dept, self.resp)
        soumission = valider_budget_departement(
            self.company, self.cycle, self.dept, self.fpa)
        self.assertEqual(soumission.statut, SoumissionBudgetDepartement.Statut.VALIDE)
