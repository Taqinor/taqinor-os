"""NTASS23 — Registre cyber-assurance et clauses IT.

Critère d'acceptation : une police cyber affiche ses clauses spécifiques dans
un bloc dédié, éditable en JSON structuré côté écran."""
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


class CyberClausesTests(TestCase):
    BASE = '/api/django/assurances/polices/'

    def setUp(self):
        self.company = make_company('assurances-p23', 'P23')
        self.user = make_user(self.company, 'assur-p23')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')

    def test_creer_police_cyber_avec_clauses_json(self):
        api = auth(self.user)
        today = datetime.date.today()
        clauses = {
            'plafond_ransomware': 500000,
            'notification_cndp_heures': 72,
            'couverture_perte_donnees': True,
            'prestataire_forensic': 'CyberDefense SARL',
        }
        resp = api.post(self.BASE, {
            'assureur': self.assureur.id,
            'numero_police': 'CYB-2026-001',
            'type_police': PoliceAssurance.TypePolice.CYBER,
            'date_effet': today.isoformat(),
            'date_echeance': (today + datetime.timedelta(days=365)).isoformat(),
            'cyber_clauses': clauses,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['cyber_clauses'], clauses)

        police = PoliceAssurance.objects.get(id=resp.data['id'])
        self.assertEqual(police.cyber_clauses['notification_cndp_heures'], 72)

    def test_cyber_clauses_defaut_dict_vide(self):
        police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='CYB-2026-002',
            type_police=PoliceAssurance.TypePolice.CYBER,
            date_effet=datetime.date.today(),
            date_echeance=datetime.date.today() + datetime.timedelta(days=365))
        self.assertEqual(police.cyber_clauses, {})
