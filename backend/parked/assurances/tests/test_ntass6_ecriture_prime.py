"""NTASS6 — Proposition d'écriture comptable sur échéance de prime.

Critère d'acceptation : proposer une écriture sur une échéance de prime crée
une ``EcritureComptable`` brouillon équilibrée, jamais validée automatiquement.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.assurances.models import Assureur, EcheancePrime, PoliceAssurance
from apps.assurances.services import proposer_ecriture_prime
from apps.compta.models import EcritureComptable

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class ProposerEcriturePrimeTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p6', 'P6')
        self.user = make_user(self.company, 'assur-p6')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-040',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=datetime.date(2026, 1, 1),
            date_echeance=datetime.date(2027, 1, 1),
            prime_annuelle_ht=Decimal('12000.00'))
        self.echeance = EcheancePrime.objects.create(
            company=self.company, police=self.police,
            date_echeance_paiement=datetime.date(2026, 1, 1),
            montant=Decimal('12000.00'),
            periodicite=EcheancePrime.Periodicite.ANNUELLE)

    def test_proposer_ecriture_cree_brouillon_equilibre(self):
        ecriture = proposer_ecriture_prime(self.echeance, user=self.user)

        self.assertEqual(ecriture.statut, EcritureComptable.Statut.BROUILLON)
        lignes = ecriture.lignes.all()
        total_debit = sum(ligne.debit for ligne in lignes)
        total_credit = sum(ligne.credit for ligne in lignes)
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('12000.00'))

        self.echeance.refresh_from_db()
        self.assertEqual(self.echeance.ecriture_ref, ecriture.id)
        self.assertEqual(
            self.echeance.statut, EcheancePrime.Statut.PROPOSEE_COMPTA)

    def test_action_api_proposer_ecriture(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post(
            '/api/django/assurances/echeances-prime/'
            f'{self.echeance.id}/proposer-ecriture/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            resp.data['ecriture_statut'], EcritureComptable.Statut.BROUILLON)
