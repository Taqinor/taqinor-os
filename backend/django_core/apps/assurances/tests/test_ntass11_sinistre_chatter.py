"""NTASS11 — ``SinistreActivity`` (chatter sinistre).

Critère d'acceptation : passer un sinistre de ``declare`` à ``en_expertise``
logge automatiquement l'entrée avec date et auteur."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, PoliceAssurance, SinistreActivity,
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


class SinistreChatterTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p11', 'P11')
        self.user = make_user(self.company, 'assur-p11')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-011',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-100',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE,
            statut=DeclarationSinistre.Statut.DECLARE)

    def test_passage_en_expertise_loggue_auteur_et_date(self):
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/assurances/declarations-sinistre/{self.declaration.id}/',
            {'statut': DeclarationSinistre.Statut.EN_EXPERTISE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        entree = SinistreActivity.objects.get(
            declaration=self.declaration, champ='statut')
        self.assertEqual(entree.ancienne_valeur, DeclarationSinistre.Statut.DECLARE)
        self.assertEqual(
            entree.nouvelle_valeur, DeclarationSinistre.Statut.EN_EXPERTISE)
        self.assertEqual(entree.user, self.user)
        self.assertIsNotNone(entree.created_at)

    def test_noter_et_historique(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/assurances/declarations-sinistre/'
            f'{self.declaration.id}/noter/',
            {'body': 'Expert mandaté, RDV la semaine prochaine.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = api.get(
            '/api/django/assurances/declarations-sinistre/'
            f'{self.declaration.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        kinds = [e['kind'] for e in resp.data]
        self.assertIn(SinistreActivity.Kind.CREATION, kinds)
        self.assertIn(SinistreActivity.Kind.NOTE, kinds)
