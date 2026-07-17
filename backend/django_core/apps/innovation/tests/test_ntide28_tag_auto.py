"""Tests du tag automatique de campagne (NTIDE28).

Couvre : ``services.maybe_apply_campagne_tag`` (applique le ``tag_auto`` de
la campagne active matchant l'utilisateur, no-op sans campagne/sans
tag_auto), et le branchement bout-en-bout via ``POST /idees/`` (l'auteur
d'une idée proposée pendant une campagne active reçoit le tag, un tiers
hors segment ne le reçoit pas).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import CampagneInnovation, Idee
from apps.records.models import Tag, TaggedItem
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


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def tags_of(idee):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Idee)
    tagged = TaggedItem.objects.filter(content_type=ct, object_id=idee.id)
    return set(Tag.objects.filter(id__in=tagged.values('tag_id')).values_list('nom', flat=True))


class MaybeApplyCampagneTagTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide28-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')

    def test_applies_tag_when_user_matches_active_campaign(self):
        tech = make_user(self.co_a, 'ntide28-tech', role=self.role_tech)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, tag_auto='Pompage')
        idee = Idee.objects.create(company=self.co_a, titre='Idée', auteur=tech)
        services.maybe_apply_campagne_tag(idee, tech)
        self.assertEqual(tags_of(idee), {'Pompage'})

    def test_noop_without_matching_campagne(self):
        tech = make_user(self.co_a, 'ntide28-tech2', role=self.role_tech)
        idee = Idee.objects.create(company=self.co_a, titre='Idée', auteur=tech)
        services.maybe_apply_campagne_tag(idee, tech)
        self.assertEqual(tags_of(idee), set())

    def test_noop_when_campagne_has_no_tag_auto(self):
        tech = make_user(self.co_a, 'ntide28-tech3', role=self.role_tech)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Sans tag', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE)
        idee = Idee.objects.create(company=self.co_a, titre='Idée', auteur=tech)
        services.maybe_apply_campagne_tag(idee, tech)
        self.assertEqual(tags_of(idee), set())

    def test_tag_stays_manually_changeable(self):
        """Le tag auto-appliqué n'est pas verrouillé : retirable comme tout
        autre tag (même mécanique que ``bulk_remove_tag``)."""
        tech = make_user(self.co_a, 'ntide28-tech4', role=self.role_tech)
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, tag_auto='Pompage')
        idee = Idee.objects.create(company=self.co_a, titre='Idée', auteur=tech)
        services.maybe_apply_campagne_tag(idee, tech)
        services.bulk_remove_tag(self.co_a, [idee.id], 'Pompage')
        self.assertEqual(tags_of(idee), set())


class ProposeIdeeAutoTagApiTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide28-api-a', 'A')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.role_com = make_role(self.co_a, 'Commercial')
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, tag_auto='Pompage')

    def test_matching_user_idea_gets_auto_tag(self):
        tech = make_user(self.co_a, 'ntide28-api-tech', role=self.role_tech)
        resp = auth(tech).post(self.BASE, {'titre': 'Nouvelle idée'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        idee = Idee.objects.get(id=resp.data['id'])
        self.assertEqual(tags_of(idee), {'Pompage'})

    def test_non_matching_user_idea_has_no_auto_tag(self):
        commercial = make_user(self.co_a, 'ntide28-api-com', role=self.role_com)
        resp = auth(commercial).post(self.BASE, {'titre': 'Autre idée'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        idee = Idee.objects.get(id=resp.data['id'])
        self.assertEqual(tags_of(idee), set())
