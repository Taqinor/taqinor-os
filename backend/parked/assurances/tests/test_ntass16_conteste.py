"""NTASS16 — Bascule vers contentieux (string-FK vers futur NTJUR).

Critère d'acceptation : un sinistre refusé marqué ``conteste=True`` reste
consultable et prêt à être repris par le futur module contentieux sans
duplication de données."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, PoliceAssurance,
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


class MarquerContesteTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p16', 'P16')
        self.user = make_user(self.company, 'assur-p16')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-016',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-600',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE,
            statut=DeclarationSinistre.Statut.REFUSE)

    def test_marquer_conteste_conserve_statut_refuse(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/assurances/declarations-sinistre/'
            f'{self.declaration.id}/marquer-conteste/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['conteste'])
        self.assertEqual(resp.data['statut'], DeclarationSinistre.Statut.REFUSE)

        self.declaration.refresh_from_db()
        self.assertTrue(self.declaration.conteste)
        # Aucun dossier contentieux créé ici (NTJUR le référence en retour).
        self.assertIsNone(self.declaration.dossier_contentieux_ref)

        # Reste consultable en lecture.
        resp = api.get(
            f'/api/django/assurances/declarations-sinistre/{self.declaration.id}/')
        self.assertEqual(resp.status_code, 200)
