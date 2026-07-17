"""NTASS10 — Modèle ``DeclarationSinistre`` (transverse, hors véhicule).

Critère d'acceptation : une déclaration de sinistre incendie sur un site est
créée, numérotée ``SIN-<année>-001``, liée à la police multirisque
correspondante."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, DeclarationSinistre, PoliceAssurance

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


class DeclarationSinistreApiTests(TestCase):
    BASE = '/api/django/assurances/declarations-sinistre/'

    def setUp(self):
        self.company = make_company('assurances-p10', 'P10')
        self.user = make_user(self.company, 'assur-p10')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-010',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))

    def test_declaration_incendie_numerotee_et_liee_a_la_police(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'police': self.police.id,
            'date_survenance': datetime.date.today().isoformat(),
            'nature_sinistre': 'Incendie électrique dans le dépôt',
            'type_sinistre': DeclarationSinistre.TypeSinistre.INCENDIE,
            'montant_estime_degats': '80000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        annee = datetime.date.today().year
        self.assertEqual(resp.data['numero_dossier'], f'SIN-{annee}-001')

        declaration = DeclarationSinistre.objects.get(id=resp.data['id'])
        self.assertEqual(declaration.police_id, self.police.id)
        self.assertEqual(declaration.company, self.company)

    def test_deuxieme_declaration_incremente_le_numero(self):
        api = auth(self.user)
        for _ in range(2):
            resp = api.post(self.BASE, {
                'police': self.police.id,
                'date_survenance': datetime.date.today().isoformat(),
                'type_sinistre': DeclarationSinistre.TypeSinistre.VOL,
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
        annee = datetime.date.today().year
        numeros = sorted(
            DeclarationSinistre.objects.filter(
                company=self.company).values_list('reference', flat=True))
        self.assertEqual(numeros, [f'SIN-{annee}-001', f'SIN-{annee}-002'])
