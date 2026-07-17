"""NTASS20 — Registre consolidé « assurances par actif » (vue transverse).

Critère d'acceptation : interroger la couverture d'un véhicule retourne à la
fois toute police multirisque d'entreprise qui le couvre, sans doublon de
données (la police auto flotte est résolue via flotte.selectors si l'app le
permet)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    ActifCouvert, Assureur, PoliceAssurance,
)
from apps.assurances.selectors import couverture_par_actif

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


class CouvertureParActifTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p20', 'P20')
        self.user = make_user(self.company, 'assur-p20')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-020',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365),
            statut=PoliceAssurance.Statut.ACTIVE)
        ActifCouvert.objects.create(
            company=self.company, police=self.police,
            type_actif=ActifCouvert.TypeActif.VEHICULE, actif_ref=555,
            actif_libelle='Camion Iveco')

    def test_selector_retourne_police_entreprise_couvrant_le_vehicule(self):
        data = couverture_par_actif(
            self.company, ActifCouvert.TypeActif.VEHICULE, 555)
        numeros = [p['numero_police'] for p in data['polices_entreprise']]
        self.assertIn('MR-2026-020', numeros)
        # Aucune police flotte pour ce véhicule fictif → liste vide, pas d'erreur.
        self.assertEqual(data['polices_flotte'], [])

    def test_endpoint_couverture_actif(self):
        api = auth(self.user)
        resp = api.get('/api/django/assurances/couverture-actif/', {
            'type_actif': ActifCouvert.TypeActif.VEHICULE, 'actif_ref': 555})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['polices_entreprise']), 1)

    def test_endpoint_exige_parametres(self):
        api = auth(self.user)
        resp = api.get('/api/django/assurances/couverture-actif/')
        self.assertEqual(resp.status_code, 400)
