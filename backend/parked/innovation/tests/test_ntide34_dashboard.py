"""Tests du dashboard campagnes « Nos campagnes innovation » (NTIDE34).

Couvre : ``selectors.tableau_bord_campagnes`` (cartes actives/fermées/
brouillons, top campagnes par idées reçues, taux de réalisation global) et
l'endpoint ``GET /api/django/innovation/campagnes/tableau-bord/`` (palier
admin, IdeasSeeAll)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
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


class TableauBordCampagnesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide34-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech = make_user(self.co_a, 'ntide34-tech', role=self.role_tech)

    def test_cards_count_by_statut(self):
        CampagneInnovation.objects.create(
            company=self.co_a, nom='A1', statut=CampagneInnovation.Statut.ACTIVE)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='A2', statut=CampagneInnovation.Statut.ACTIVE)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='F1', statut=CampagneInnovation.Statut.FERMEE)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='B1', statut=CampagneInnovation.Statut.BROUILLON)
        data = selectors.tableau_bord_campagnes(self.co_a)
        self.assertEqual(data['actives'], 2)
        self.assertEqual(data['fermees'], 1)
        self.assertEqual(data['brouillons'], 1)

    def test_top_campagnes_by_ideas_received(self):
        # Segments DIFFÉRENTS : ``rapport_campagne`` compte les idées des
        # utilisateurs matchant le SEGMENT (pas une FK idée→campagne), donc
        # deux campagnes visant le même segment auraient le même compte.
        role_com = make_role(self.co_a, 'Commercial')
        make_user(self.co_a, 'ntide34-com', role=role_com)
        camp_forte = CampagneInnovation.objects.create(
            company=self.co_a, nom='Forte', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Faible', segment=['Commercial'],
            statut=CampagneInnovation.Statut.ACTIVE)
        Idee.objects.create(company=self.co_a, auteur=self.tech, titre='Idée 1')
        Idee.objects.create(company=self.co_a, auteur=self.tech, titre='Idée 2')
        data = selectors.tableau_bord_campagnes(self.co_a)
        top_noms = [c['nom'] for c in data['top_campagnes']]
        self.assertEqual(top_noms[0], 'Forte')
        self.assertEqual(data['top_campagnes'][0]['nb_idees_proposees'], 2)
        self.assertEqual(camp_forte.nom, 'Forte')

    def test_taux_realisation(self):
        Idee.objects.create(
            company=self.co_a, auteur=self.tech, titre='Réalisée',
            statut=Idee.Statut.REALISEE)
        Idee.objects.create(
            company=self.co_a, auteur=self.tech, titre='Ouverte')
        data = selectors.tableau_bord_campagnes(self.co_a)
        self.assertEqual(data['taux_realisation'], 0.5)

    def test_taux_realisation_zero_without_ideas(self):
        data = selectors.tableau_bord_campagnes(self.co_a)
        self.assertEqual(data['taux_realisation'], 0.0)


class TableauBordCampagnesEndpointTests(TestCase):
    BASE = '/api/django/innovation/campagnes/tableau-bord/'

    def setUp(self):
        self.co_a = make_company('innov-ntide34-api-a', 'A')
        self.admin = make_user(self.co_a, 'ntide34-api-admin', role_legacy='admin')
        self.normal = make_user(self.co_a, 'ntide34-api-normal')

    def test_admin_can_view(self):
        resp = auth(self.admin).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('actives', resp.data)
        self.assertIn('top_campagnes', resp.data)
        self.assertIn('taux_realisation', resp.data)

    def test_normal_role_refused(self):
        resp = auth(self.normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
