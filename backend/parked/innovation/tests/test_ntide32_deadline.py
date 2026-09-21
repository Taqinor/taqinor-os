"""Tests de la deadline de campagne (NTIDE32).

Couvre : une campagne ``active`` en base dont ``date_fin`` est PASSÉE n'est
plus renvoyée par ``campagne_active_pour_utilisateur`` (ni prise en compte
par le tag auto NTIDE28, qui la réutilise) ; ``campagne_expiree_pour_
utilisateur`` la retrouve pour afficher « Campagne fermée le XX » ;
l'endpoint ``incitation`` bascule ``fermee: true`` avec le nom/la date de la
campagne expirée. Les idées déjà proposées restent visibles (aucune
suppression déclenchée par la deadline)."""
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


class CampagneDeadlineTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide32-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech = make_user(self.co_a, 'ntide32-tech', role=self.role_tech)

    def test_expired_campaign_not_returned_as_active(self):
        hier = timezone.now().date() - datetime.timedelta(days=1)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, date_fin=hier)
        self.assertIsNone(selectors.campagne_active_pour_utilisateur(self.tech))

    def test_campaign_without_date_fin_still_active(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Sans deadline', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE)
        self.assertEqual(
            selectors.campagne_active_pour_utilisateur(self.tech), camp)

    def test_campaign_with_future_date_fin_still_active(self):
        demain = timezone.now().date() + datetime.timedelta(days=1)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Bientôt fermée', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, date_fin=demain)
        self.assertEqual(
            selectors.campagne_active_pour_utilisateur(self.tech), camp)

    def test_expiree_selector_finds_expired_matching_campaign(self):
        hier = timezone.now().date() - datetime.timedelta(days=1)
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, date_fin=hier)
        self.assertEqual(
            selectors.campagne_expiree_pour_utilisateur(self.tech), camp)

    def test_ideas_remain_visible_after_expiration(self):
        hier = timezone.now().date() - datetime.timedelta(days=1)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, date_fin=hier,
            tag_auto='Pompage')
        idee = Idee.objects.create(
            company=self.co_a, auteur=self.tech, titre='Idée pompage')
        # Aucune suppression/masquage déclenché par l'expiration de la campagne.
        self.assertTrue(Idee.objects.filter(pk=idee.pk, archived=False).exists())


class IncitationEndpointFermeeTests(TestCase):
    BASE = '/api/django/innovation/campagnes/incitation/'

    def setUp(self):
        self.co_a = make_company('innov-ntide32-api-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.tech = make_user(self.co_a, 'ntide32-api-tech', role=self.role_tech)

    def test_shows_fermee_when_deadline_passed(self):
        hier = timezone.now().date() - datetime.timedelta(days=1)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, date_fin=hier)
        resp = auth(self.tech).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['campagne'])
        self.assertTrue(resp.data['fermee'])
        self.assertEqual(resp.data['campagne_fermee'], 'Pompage')
        self.assertEqual(str(resp.data['date_fin']), str(hier))

    def test_no_campaign_at_all_returns_fermee_false(self):
        resp = auth(self.tech).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['campagne'])
        self.assertFalse(resp.data['fermee'])
