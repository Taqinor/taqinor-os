"""Tests XRH13 — Import de pointages externes (pointeuse biométrique, CSV).

Couvre :
* un CSV de 10 lignes crée les pointages mappés (idempotent par
  (employe, horodatage)) ;
* ré-import = 0 doublon créé ;
* une ligne sans mapping est listée en erreur (jamais silencieusement
  ignorée) ;
* isolation société du mappage (device_user_id d'une autre société invisible).
"""
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, EmployeDeviceMap, Pointage

User = get_user_model()

IMPORT_URL = '/api/django/rh/pointages/importer/'
MAPS_URL = '/api/django/rh/devices-employe-map/'


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


def _csv_file(text):
    buf = BytesIO(text.encode('utf-8'))
    buf.name = 'pointages.csv'
    return buf


class ImportPointagesCsvTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-a', 'A')
        self.rh = make_user(self.co, 'imp-rh')
        self.emp1 = DossierEmploye.objects.create(
            company=self.co, matricule='I1', nom='Amrani', prenom='Sara')
        self.emp2 = DossierEmploye.objects.create(
            company=self.co, matricule='I2', nom='Benjelloun', prenom='Omar')
        EmployeDeviceMap.objects.create(
            company=self.co, employe=self.emp1, device_user_id='DEV001')
        EmployeDeviceMap.objects.create(
            company=self.co, employe=self.emp2, device_user_id='DEV002')

    def _csv_10_lignes(self):
        header = 'device_user_id,horodatage,sens\n'
        rows = []
        for i in range(5):
            rows.append(f'DEV001,2026-07-0{i + 1}T08:00:00,in')
            rows.append(f'DEV002,2026-07-0{i + 1}T08:05:00,in')
        return header + '\n'.join(rows) + '\n'

    def test_import_10_lignes_cree_pointages(self):
        resp = auth(self.rh).post(
            IMPORT_URL, {'file': _csv_file(self._csv_10_lignes())},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['crees']), 10)
        self.assertEqual(len(resp.data['erreurs']), 0)
        self.assertEqual(
            Pointage.objects.filter(company=self.co).count(), 10)

    def test_reimport_zero_doublon(self):
        text = self._csv_10_lignes()
        auth(self.rh).post(
            IMPORT_URL, {'file': _csv_file(text)}, format='multipart')
        resp = auth(self.rh).post(
            IMPORT_URL, {'file': _csv_file(text)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['crees']), 0)
        self.assertEqual(len(resp.data['doublons']), 10)
        self.assertEqual(
            Pointage.objects.filter(company=self.co).count(), 10)

    def test_ligne_sans_mapping_rapportee_en_erreur(self):
        text = (
            'device_user_id,horodatage,sens\n'
            'DEVXXX,2026-07-01T08:00:00,in\n'
            'DEV001,2026-07-01T08:00:00,in\n'
        )
        resp = auth(self.rh).post(
            IMPORT_URL, {'file': _csv_file(text)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['erreurs']), 1)
        self.assertEqual(resp.data['erreurs'][0]['device_user_id'], 'DEVXXX')
        self.assertEqual(len(resp.data['crees']), 1)

    def test_horodatage_invalide_rapporte_en_erreur(self):
        text = (
            'device_user_id,horodatage,sens\n'
            'DEV001,pas-une-date,in\n'
        )
        resp = auth(self.rh).post(
            IMPORT_URL, {'file': _csv_file(text)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['erreurs']), 1)

    def test_isolation_societe_mapping(self):
        co_b = make_company('imp-b', 'B')
        rh_b = make_user(co_b, 'imp-rh-b')
        emp_b = DossierEmploye.objects.create(
            company=co_b, matricule='IB1', nom='X', prenom='Y')
        EmployeDeviceMap.objects.create(
            company=co_b, employe=emp_b, device_user_id='DEV001')

        # DEV001 dans la société A pointe emp1 de A, pas emp_b de B.
        text = 'device_user_id,horodatage,sens\nDEV001,2026-07-01T08:00:00,in\n'
        resp = auth(self.rh).post(
            IMPORT_URL, {'file': _csv_file(text)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['crees']), 1)
        self.assertEqual(
            Pointage.objects.filter(company=self.co, employe=self.emp1)
            .count(), 1)
        self.assertEqual(Pointage.objects.filter(company=co_b).count(), 0)
        self.assertTrue(rh_b)  # utilisé pour la lisibilité du test

    def test_sans_fichier_400(self):
        resp = auth(self.rh).post(IMPORT_URL, {}, format='multipart')
        self.assertEqual(resp.status_code, 400)
