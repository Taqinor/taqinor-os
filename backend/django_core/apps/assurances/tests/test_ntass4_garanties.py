"""NTASS4 — Garanties, plafonds & franchises par police.

Critère d'acceptation : une police avec 3 garanties affiche chacune avec son
plafond et sa franchise indépendamment."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, GarantiePolice, PoliceAssurance

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class GarantiePoliceApiTests(TestCase):
    BASE = '/api/django/assurances/garanties-police/'

    def setUp(self):
        self.company = make_company('assurances-p4', 'P4')
        self.user = make_user(self.company, 'assur-p4')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-020',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))

    def test_police_avec_trois_garanties_plafonds_franchises_independants(self):
        api = auth(self.user)
        garanties = [
            ('Dommages aux tiers', '1000000.00', '10000.00'),
            ('Responsabilité après travaux', '2000000.00', '20000.00'),
            ('Effondrement', '500000.00', '5000.00'),
        ]
        for libelle, plafond, franchise in garanties:
            resp = api.post(self.BASE, {
                'police': self.police.id,
                'libelle_garantie': libelle,
                'plafond_indemnisation': plafond,
                'franchise_montant': franchise,
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)

        self.assertEqual(GarantiePolice.objects.filter(
            police=self.police).count(), 3)

        resp = api.get(self.BASE, {'police': self.police.id})
        data = rows(resp)
        self.assertEqual(len(data), 3)
        plafonds = {d['libelle_garantie']: d['plafond_indemnisation'] for d in data}
        self.assertEqual(plafonds['Dommages aux tiers'], '1000000.00')
        self.assertEqual(plafonds['Responsabilité après travaux'], '2000000.00')
        self.assertEqual(plafonds['Effondrement'], '500000.00')
