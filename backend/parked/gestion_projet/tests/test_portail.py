"""Tests du portail d'avancement client (PROJ37).

Le portail PUBLIC (jeton, non authentifié) expose UNIQUEMENT l'avancement non
financier : AUCUN coût/budget/marge/``facturation_pct`` ne traverse la frontière.

Couvre : le sélecteur sanitisé n'expose aucune donnée financière ; l'endpoint
public répond avec un jeton actif ; 404 sur jeton inconnu ou révoqué ; gestion
des jetons côté admin (token généré serveur, company serveur) ; accès
Administrateur/Responsable au CRUD des jetons (403 pour ``normal``).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    Jalon,
    PhaseProjet,
    PortailProjetToken,
    Projet,
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


class PortailSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-por-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-POR', nom='P',
            budget_total=Decimal('100000'))
        PhaseProjet.objects.create(
            company=self.co, projet=self.projet,
            type_phase=PhaseProjet.TypePhase.POSE, libelle='Pose',
            avancement_pct=40, ordre=3)
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 1), facturation_pct=Decimal('30'))

    def test_aucune_donnee_financiere_exposee(self):
        data = selectors.portail_avancement_client(self.projet)
        # Pas de budget/marge au niveau projet.
        self.assertNotIn('budget_total', data['projet'])
        self.assertNotIn('marge_reelle', data)
        # Phases sans charge ni coût.
        for phase in data['phases']:
            self.assertNotIn('charge_estimee', phase)
        # Jalons SANS facturation_pct (échéancier de paiement interne).
        for jalon in data['jalons']:
            self.assertNotIn('facturation_pct', jalon)
        self.assertEqual(len(data['jalons']), 1)
        self.assertEqual(data['jalons'][0]['libelle'], 'Acompte')


class PortailPublicApiTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-por-pub', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-PUB', nom='P')
        self.token_obj = PortailProjetToken.objects.create(
            company=self.co, projet=self.projet)

    def _url(self, token):
        return f'/api/django/gestion-projet/portail/{token}/'

    def test_jeton_actif_repond(self):
        api = APIClient()  # non authentifié.
        resp = api.get(self._url(self.token_obj.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['projet']['code'], 'P-PUB')

    def test_jeton_inconnu_404(self):
        api = APIClient()
        resp = api.get(self._url('inexistant'))
        self.assertEqual(resp.status_code, 404)

    def test_jeton_revoque_404(self):
        self.token_obj.actif = False
        self.token_obj.save()
        api = APIClient()
        resp = api.get(self._url(self.token_obj.token))
        self.assertEqual(resp.status_code, 404)


class PortailTokenAdminApiTests(TestCase):
    BASE = '/api/django/gestion-projet/portail-tokens/'

    def setUp(self):
        self.co_a = make_company('gp-por-a', 'A')
        self.user_a = make_user(self.co_a, 'por-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_creation_token_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'token': 'force',  # posté — doit être ignoré (généré serveur).
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PortailProjetToken.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company_id, self.co_a.id)
        self.assertNotEqual(obj.token, 'force')
        self.assertTrue(len(obj.token) >= 20)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'por-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
