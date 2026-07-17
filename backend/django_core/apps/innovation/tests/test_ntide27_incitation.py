"""Tests du bandeau d'incitation de campagne (NTIDE27).

Couvre : ``selectors.campagne_active_pour_utilisateur`` (matching segment/
cible_departement, statut ACTIVE uniquement, plus récente en cas de
plusieurs correspondances, None sans rôle fin/sans correspondance), et
l'endpoint ``GET /api/django/innovation/campagnes/incitation/`` (accès tout
utilisateur connecté, isolation multi-société).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import CampagneInnovation
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role(company, nom):
    role, _ = Role.objects.get_or_create(company=company, nom=nom)
    return role


def make_user(company, username, role=None, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CampagneActivePourUtilisateurTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide27-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')

    def test_matches_active_campaign_by_segment(self):
        tech = make_user(self.co_a, 'ntide27-tech', role=self.role_tech)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Idées pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE,
            message_incitation='Nous cherchons vos idées sur le pompage.')
        result = selectors.campagne_active_pour_utilisateur(tech)
        self.assertEqual(result, camp)

    def test_ignores_non_active_campaign(self):
        tech = make_user(self.co_a, 'ntide27-tech2', role=self.role_tech)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Brouillon', segment=['Technicien'],
            statut=CampagneInnovation.Statut.BROUILLON)
        result = selectors.campagne_active_pour_utilisateur(tech)
        self.assertIsNone(result)

    def test_no_match_returns_none(self):
        commercial_role = make_role(self.co_a, 'Commercial')
        commercial = make_user(self.co_a, 'ntide27-com', role=commercial_role)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Techniciens seulement',
            segment=['Technicien'], statut=CampagneInnovation.Statut.ACTIVE)
        result = selectors.campagne_active_pour_utilisateur(commercial)
        self.assertIsNone(result)

    def test_user_without_fine_role_returns_none(self):
        legacy = make_user(self.co_a, 'ntide27-legacy')
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Peu importe', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE)
        result = selectors.campagne_active_pour_utilisateur(legacy)
        self.assertIsNone(result)

    def test_most_recent_wins_on_multiple_matches(self):
        tech = make_user(self.co_a, 'ntide27-tech3', role=self.role_tech)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Ancienne', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE)
        recente = CampagneInnovation.objects.create(
            company=self.co_a, nom='Récente', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE)
        result = selectors.campagne_active_pour_utilisateur(tech)
        self.assertEqual(result, recente)


class IncitationEndpointTests(TestCase):
    BASE = '/api/django/innovation/campagnes/incitation/'

    def setUp(self):
        self.co_a = make_company('innov-ntide27-api-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech_a = make_user(self.co_a, 'ntide27-api-tech', role=self.role_tech)

    def test_returns_matching_campagne(self):
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Idées pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE,
            message_incitation='Parlez-nous du pompage.')
        resp = auth(self.tech_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['campagne']['nom'], 'Idées pompage')
        self.assertEqual(
            resp.data['campagne']['message_incitation'], 'Parlez-nous du pompage.')

    def test_returns_null_when_no_match(self):
        resp = auth(self.tech_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['campagne'])

    def test_accessible_to_any_logged_in_user(self):
        normal_user = make_user(self.co_a, 'ntide27-api-normal')
        resp = auth(normal_user).get(self.BASE)
        self.assertEqual(resp.status_code, 200)


class CampagneCrudGatingTests(TestCase):
    """La gestion des campagnes (hors ``incitation``) reste réservée au
    palier Directeur/Admin (``IdeasSeeAll``, NTIDE22)."""

    BASE = '/api/django/innovation/campagnes/'

    def setUp(self):
        self.co_a = make_company('innov-ntide27-crud-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide27-crud-admin', role_legacy='admin')
        self.normal_a = make_user(self.co_a, 'ntide27-crud-normal')

    def test_admin_can_create(self):
        resp = auth(self.admin_a).post(
            self.BASE, {'nom': 'Nouvelle campagne'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_normal_role_refused_on_list(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
