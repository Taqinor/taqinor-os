"""NTASS8 — Alertes de renouvellement.

Critère d'acceptation : une police échéant dans 25 jours apparaît sous
``?within=30`` et pas sous ``?within=10``."""
import datetime

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, PoliceAssurance
from apps.assurances.selectors import polices_expirantes
from apps.notifications.models import Notification

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


class AlertesRenouvellementTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p8', 'P8')
        self.user = make_user(self.company, 'assur-p8')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-050',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=today - datetime.timedelta(days=340),
            date_echeance=today + datetime.timedelta(days=25))

    def test_police_expire_25j_apparait_sous_30_pas_sous_10(self):
        self.assertIn(
            self.police, list(polices_expirantes(self.company, within=30)))
        self.assertNotIn(
            self.police, list(polices_expirantes(self.company, within=10)))

    def test_endpoint_expirantes(self):
        api = auth(self.user)
        resp = api.get(
            '/api/django/assurances/polices/expirantes/', {'within': 30})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

        resp = api.get(
            '/api/django/assurances/polices/expirantes/', {'within': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_commande_notifie_une_seule_fois(self):
        call_command('alertes_expiration_assurances')
        notifs = Notification.objects.filter(
            recipient=self.user, event_type='assurance_police_expirante')
        self.assertEqual(notifs.count(), 1)
