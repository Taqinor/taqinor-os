"""Tests du rapport de campagne (NTIDE29).

Couvre : ``selectors.rapport_campagne`` (nb ciblés, nb proposées depuis
date_debut, top votes, taux de conversion), et l'endpoint
``GET /campagnes/{id}/rapport/`` (palier Directeur/Admin, isolation
multi-société via 404).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import CampagneInnovation, Idee
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


class RapportCampagneSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide29-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech1 = make_user(self.co_a, 'ntide29-tech1', role=self.role_tech)
        self.tech2 = make_user(self.co_a, 'ntide29-tech2', role=self.role_tech)

    def test_counts_targeted_users(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'])
        rapport = selectors.rapport_campagne(camp)
        self.assertEqual(rapport['nb_utilisateurs_cibles'], 2)

    def test_counts_ideas_from_targeted_users_only(self):
        Idee.objects.create(company=self.co_a, titre='De tech1', auteur=self.tech1)
        commercial_role = make_role(self.co_a, 'Commercial')
        commercial = make_user(self.co_a, 'ntide29-com', role=commercial_role)
        Idee.objects.create(company=self.co_a, titre='Hors segment', auteur=commercial)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'])
        rapport = selectors.rapport_campagne(camp)
        self.assertEqual(rapport['nb_idees_proposees'], 1)

    def test_excludes_ideas_before_date_debut(self):
        old = Idee.objects.create(company=self.co_a, titre='Vieille', auteur=self.tech1)
        Idee.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=10))
        Idee.objects.create(company=self.co_a, titre='Récente', auteur=self.tech1)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            date_debut=(timezone.now() - datetime.timedelta(days=1)).date())
        rapport = selectors.rapport_campagne(camp)
        self.assertEqual(rapport['nb_idees_proposees'], 1)

    def test_top_idees_ordered_by_votes(self):
        Idee.objects.create(
            company=self.co_a, titre='Basse', auteur=self.tech1, votes_count=1)
        Idee.objects.create(
            company=self.co_a, titre='Haute', auteur=self.tech2, votes_count=9)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'])
        rapport = selectors.rapport_campagne(camp)
        self.assertEqual(rapport['top_idees'][0]['titre'], 'Haute')

    def test_conversion_rate(self):
        Idee.objects.create(company=self.co_a, titre='De tech1', auteur=self.tech1)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'])
        rapport = selectors.rapport_campagne(camp)
        self.assertEqual(rapport['taux_conversion'], 0.5)  # 1 sur 2 ciblés

    def test_no_target_zero_conversion_no_crash(self):
        camp = CampagneInnovation.objects.create(company=self.co_a, nom='Vide')
        rapport = selectors.rapport_campagne(camp)
        self.assertEqual(rapport['nb_utilisateurs_cibles'], 0)
        self.assertEqual(rapport['taux_conversion'], 0.0)


class RapportCampagneApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide29-api-a', 'A')
        self.co_b = make_company('innov-ntide29-api-b', 'B')
        self.admin_a = make_user(self.co_a, 'ntide29-api-admin', role_legacy='admin')
        self.normal_a = make_user(self.co_a, 'ntide29-api-normal')
        self.camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'])

    def test_admin_can_view_rapport(self):
        resp = auth(self.admin_a).get(
            f'/api/django/innovation/campagnes/{self.camp.id}/rapport/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('nb_utilisateurs_cibles', resp.data)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).get(
            f'/api/django/innovation/campagnes/{self.camp.id}/rapport/')
        self.assertEqual(resp.status_code, 403)

    def test_cross_tenant_404(self):
        user_b = make_user(self.co_b, 'ntide29-api-b-user', role_legacy='admin')
        resp = auth(user_b).get(
            f'/api/django/innovation/campagnes/{self.camp.id}/rapport/')
        self.assertEqual(resp.status_code, 404)
