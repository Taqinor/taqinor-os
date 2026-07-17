"""NTASS13 — Écriture comptable proposée sur indemnisation reçue.

Critère d'acceptation : proposer l'écriture sur une indemnisation encaissée
crée une ligne équilibrée en brouillon, visible dans le grand livre après
validation manuelle compta."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, IndemnisationSinistre, PoliceAssurance,
)
from apps.assurances.services import proposer_ecriture_indemnisation
from apps.compta.models import EcritureComptable

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class ProposerEcritureIndemnisationTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p13', 'P13')
        self.user = make_user(self.company, 'assur-p13')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-013',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-300',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE)
        self.indemnisation = IndemnisationSinistre.objects.create(
            company=self.company, declaration=self.declaration,
            montant_reclame=Decimal('50000.00'),
            franchise_appliquee=Decimal('5000.00'),
            montant_indemnise=Decimal('45000.00'),
            date_versement=today)

    def test_proposer_ecriture_indemnisation_brouillon_equilibre(self):
        ecriture = proposer_ecriture_indemnisation(
            self.indemnisation, user=self.user)
        self.assertEqual(ecriture.statut, EcritureComptable.Statut.BROUILLON)
        lignes = ecriture.lignes.all()
        total_debit = sum(ligne.debit for ligne in lignes)
        total_credit = sum(ligne.credit for ligne in lignes)
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('45000.00'))

        self.indemnisation.refresh_from_db()
        self.assertEqual(self.indemnisation.ecriture_ref, ecriture.id)

    def test_action_api_proposer_ecriture_indemnisation(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post(
            '/api/django/assurances/declarations-sinistre/'
            f'{self.declaration.id}/proposer-ecriture-indemnisation/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            resp.data['ecriture_statut'], EcritureComptable.Statut.BROUILLON)
