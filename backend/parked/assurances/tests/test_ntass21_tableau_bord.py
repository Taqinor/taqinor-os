"""NTASS21 — Tableau de bord assurances.

Critère d'acceptation : le tableau de bord affiche la prime totale annuelle et
le taux de sinistralité (sinistres/an ÷ polices actives)."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, PoliceAssurance,
)
from apps.assurances.selectors import tableau_bord_assurances

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


class TableauBordAssurancesTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p21', 'P21')
        self.user = make_user(self.company, 'assur-p21')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        for i, prime in enumerate([Decimal('12000.00'), Decimal('8000.00')]):
            PoliceAssurance.objects.create(
                company=self.company, assureur=self.assureur,
                numero_police=f'MR-2026-02{i}',
                type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
                date_effet=today,
                date_echeance=today + datetime.timedelta(days=365),
                prime_annuelle_ht=prime,
                statut=PoliceAssurance.Statut.ACTIVE)
        # Un sinistre survenu il y a 10 jours (dans les 12 mois).
        police = PoliceAssurance.objects.filter(company=self.company).first()
        DeclarationSinistre.objects.create(
            company=self.company, police=police, reference='SIN-2026-700',
            date_survenance=today - datetime.timedelta(days=10),
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE)

    def test_selector_prime_totale_et_taux_sinistralite(self):
        data = tableau_bord_assurances(self.company)
        self.assertEqual(data['nb_polices_actives'], 2)
        self.assertEqual(data['prime_annuelle_totale'], Decimal('20000.00'))
        # 1 sinistre / 2 polices actives = 0.5.
        self.assertEqual(data['taux_sinistralite'], 0.5)

    def test_endpoint_tableau_bord(self):
        api = auth(self.user)
        resp = api.get('/api/django/assurances/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_polices_actives'], 2)
        self.assertIn('taux_sinistralite', resp.data)
