"""Tests du sélecteur ``users_for_campaign`` (NTIDE26).

Couvre : filtrage par rôle FIN (``role.nom``) figurant dans ``segment`` ou
``cible_departement``, queryset vide sans cible, isolation multi-société,
utilisateurs sans rôle fin jamais ciblés.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

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


def make_user(company, username, role=None):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


class UsersForCampaignTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide26-a', 'A')
        self.co_b = make_company('innov-ntide26-b', 'B')
        self.role_tech_a = make_role(self.co_a, 'Technicien')
        self.role_com_a = make_role(self.co_a, 'Commercial')
        self.role_tech_b = make_role(self.co_b, 'Technicien')

    def test_filters_by_segment_role(self):
        tech = make_user(self.co_a, 'ntide26-tech', role=self.role_tech_a)
        make_user(self.co_a, 'ntide26-com', role=self.role_com_a)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Campagne', segment=['Technicien'])
        result = list(selectors.users_for_campaign(self.co_a, camp))
        self.assertEqual(result, [tech])

    def test_filters_by_cible_departement_fallback(self):
        tech = make_user(self.co_a, 'ntide26-tech2', role=self.role_tech_a)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Campagne', cible_departement='Technicien')
        result = list(selectors.users_for_campaign(self.co_a, camp))
        self.assertEqual(result, [tech])

    def test_no_target_returns_empty(self):
        make_user(self.co_a, 'ntide26-notarget', role=self.role_tech_a)
        camp = CampagneInnovation.objects.create(company=self.co_a, nom='Vide')
        result = list(selectors.users_for_campaign(self.co_a, camp))
        self.assertEqual(result, [])

    def test_user_without_role_never_targeted(self):
        make_user(self.co_a, 'ntide26-norole')
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Campagne', segment=['Technicien'])
        result = list(selectors.users_for_campaign(self.co_a, camp))
        self.assertEqual(result, [])

    def test_isolated_per_company(self):
        make_user(self.co_b, 'ntide26-tech-b', role=self.role_tech_b)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Campagne', segment=['Technicien'])
        result = list(selectors.users_for_campaign(self.co_a, camp))
        self.assertEqual(result, [])

    def test_multi_role_segment(self):
        tech = make_user(self.co_a, 'ntide26-tech3', role=self.role_tech_a)
        com = make_user(self.co_a, 'ntide26-com2', role=self.role_com_a)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Campagne',
            segment=['Technicien', 'Commercial'])
        result = set(selectors.users_for_campaign(self.co_a, camp))
        self.assertEqual(result, {tech, com})
