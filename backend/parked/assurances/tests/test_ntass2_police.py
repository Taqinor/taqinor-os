"""NTASS2 — Modèle ``PoliceAssurance``.

Critère d'acceptation : une police DÉCENNALE créée avec échéance J+365
apparaît listée, filtrable par ``type_police``."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, PoliceAssurance

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


class PoliceAssuranceApiTests(TestCase):
    BASE = '/api/django/assurances/polices/'

    def setUp(self):
        self.company = make_company('assurances-p2', 'P2')
        self.user = make_user(self.company, 'assur-p2')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')

    def test_creer_police_decennale_apparait_listee(self):
        api = auth(self.user)
        today = datetime.date.today()
        payload = {
            'assureur': self.assureur.id,
            'numero_police': 'DEC-2026-001',
            'type_police': PoliceAssurance.TypePolice.DECENNALE,
            'date_effet': today.isoformat(),
            'date_echeance': (today + datetime.timedelta(days=365)).isoformat(),
            'prime_annuelle_ht': '12000.00',
        }
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PoliceAssurance.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.company)
        self.assertEqual(obj.type_police, PoliceAssurance.TypePolice.DECENNALE)

        # Filtrable par type_police.
        resp = api.get(self.BASE, {'type_police': 'decennale'})
        self.assertEqual(len(rows(resp)), 1)
        resp = api.get(self.BASE, {'type_police': 'cyber'})
        self.assertEqual(len(rows(resp)), 0)

    def test_unique_numero_police_par_societe(self):
        PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-002',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=datetime.date.today(),
            date_echeance=datetime.date.today() + datetime.timedelta(days=365))
        api = auth(self.user)
        payload = {
            'assureur': self.assureur.id,
            'numero_police': 'DEC-2026-002',
            'type_police': PoliceAssurance.TypePolice.DECENNALE,
            'date_effet': datetime.date.today().isoformat(),
            'date_echeance': (
                datetime.date.today() + datetime.timedelta(days=365)).isoformat(),
        }
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400)
