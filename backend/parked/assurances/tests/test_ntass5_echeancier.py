"""NTASS5 — Échéancier de primes.

Critère d'acceptation : une police annuelle à 12 000 MAD en périodicité
trimestrielle génère 4 échéances de 3 000 MAD aux bonnes dates."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, EcheancePrime, PoliceAssurance
from apps.assurances.services import generer_echeancier_prime

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EcheancierPrimeTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p5', 'P5')
        self.user = make_user(self.company, 'assur-p5')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-030',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=datetime.date(2026, 1, 15),
            date_echeance=datetime.date(2027, 1, 15),
            prime_annuelle_ht=Decimal('12000.00'))

    def test_generer_echeancier_trimestriel_quatre_echeances_3000(self):
        echeances = generer_echeancier_prime(
            self.police, EcheancePrime.Periodicite.TRIMESTRIELLE)
        self.assertEqual(len(echeances), 4)
        montants = [e.montant for e in echeances]
        self.assertEqual(montants, [Decimal('3000.00')] * 4)
        # Somme exacte de la prime annuelle.
        self.assertEqual(sum(montants), self.police.prime_annuelle_ht)
        dates = [e.date_echeance_paiement for e in echeances]
        self.assertEqual(dates, [
            datetime.date(2026, 1, 15), datetime.date(2026, 4, 15),
            datetime.date(2026, 7, 15), datetime.date(2026, 10, 15),
        ])

    def test_generer_echeancier_via_api_et_marquer_payee(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/assurances/polices/{self.police.id}/generer-echeancier/',
            {'periodicite': 'trimestrielle'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 4)

        echeance_id = resp.data[0]['id']
        resp = api.post(
            f'/api/django/assurances/echeances-prime/{echeance_id}/marquer-payee/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], EcheancePrime.Statut.PAYEE)
