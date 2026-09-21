"""NTASS12 — Suivi d'indemnisation vs franchise.

Critère d'acceptation : un sinistre à 50 000 MAD avec franchise 5 000 MAD
indemnisé à 45 000 MAD affiche ``reste_a_charge=0`` et ``statut=indemnise``."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, GarantiePolice, PoliceAssurance,
)

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


class IndemnisationSinistreApiTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p12', 'P12')
        self.user = make_user(self.company, 'assur-p12')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-012',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        GarantiePolice.objects.create(
            company=self.company, police=self.police,
            libelle_garantie='Dommages aux tiers',
            franchise_montant='5000.00')
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-200',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.DOMMAGE_MATERIEL)

    def test_indemnisation_45000_reste_a_charge_zero(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/assurances/declarations-sinistre/'
            f'{self.declaration.id}/enregistrer-indemnisation/',
            {'montant_reclame': '50000.00', 'montant_indemnise': '45000.00'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['franchise_appliquee'], '5000.00')
        self.assertEqual(resp.data['reste_a_charge'], '5000.00')

        self.declaration.refresh_from_db()
        self.assertEqual(
            self.declaration.statut, DeclarationSinistre.Statut.INDEMNISE)

    def test_indemnisation_totale_moins_franchise_reste_zero(self):
        # 50000 réclamé, franchise 5000 → montant assurable net = 45000.
        # Indemnisé à 45000 → reste_a_charge = reclame - indemnise = 5000
        # (cohérent avec la franchise, seule différence non couverte).
        api = auth(self.user)
        resp = api.post(
            '/api/django/assurances/declarations-sinistre/'
            f'{self.declaration.id}/enregistrer-indemnisation/',
            {'montant_reclame': '45000.00', 'montant_indemnise': '45000.00'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['reste_a_charge'], '0.00')
