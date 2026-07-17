"""NTASS7 — Actifs/sites couverts par police (string-FK transverse).

Critère d'acceptation : une police multirisque liste 3 sites + 2 véhicules
couverts, chaque ligne affiche un libellé lisible résolu à la volée."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import ActifCouvert, Assureur, PoliceAssurance

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


class ActifCouvertApiTests(TestCase):
    BASE = '/api/django/assurances/actifs-couverts/'

    def setUp(self):
        self.company = make_company('assurances-p7', 'P7')
        self.user = make_user(self.company, 'assur-p7')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-001',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))

    def test_police_liste_3_sites_2_vehicules_avec_libelle(self):
        api = auth(self.user)
        for i in range(3):
            resp = api.post(self.BASE, {
                'police': self.police.id,
                'type_actif': ActifCouvert.TypeActif.SITE,
                'actif_libelle': f'Site {i + 1}',
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
        for i in range(2):
            resp = api.post(self.BASE, {
                'police': self.police.id,
                'type_actif': ActifCouvert.TypeActif.VEHICULE,
                'actif_ref': 9000 + i,
                'actif_libelle': f'Véhicule fallback {i + 1}',
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)

        self.assertEqual(
            ActifCouvert.objects.filter(police=self.police).count(), 5)

        resp = api.get(self.BASE, {'police': self.police.id})
        data = rows(resp)
        self.assertEqual(len(data), 5)
        for ligne in data:
            self.assertTrue(ligne['actif_libelle'])

    def test_libelle_fallback_snapshot_sans_vehicule_correspondant(self):
        # Aucune AssuranceVehicule flotte ne correspond à cet actif_ref :
        # la résolution renvoie None, le snapshot doit s'afficher tel quel.
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'police': self.police.id,
            'type_actif': ActifCouvert.TypeActif.VEHICULE,
            'actif_ref': 123456,
            'actif_libelle': 'Camion Iveco (snapshot)',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['actif_libelle'], 'Camion Iveco (snapshot)')
