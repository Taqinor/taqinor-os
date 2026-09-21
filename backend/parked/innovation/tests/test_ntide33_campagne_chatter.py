"""Tests du chatter de campagne (NTIDE33).

Couvre : journal automatique de création + de changement des champs suivis
(statut/segment/message_incitation/tag_auto), la note manuelle (``noter``),
et l'endpoint ``historique`` (même pattern générique ``records.Activity``
que le chatter d'idée)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import CampagneInnovation
from apps.records.models import Activity
from apps.records.services import chatter_qs

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LogCampagneChangesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide33-a', 'A')
        self.admin = make_user(self.co_a, 'ntide33-admin')

    def test_logs_only_changed_tracked_fields(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage',
            statut=CampagneInnovation.Statut.BROUILLON, tag_auto='')
        anciennes = {
            champ: getattr(camp, champ) for champ in services.CAMPAGNE_CHAMPS_SUIVIS
        }
        camp.statut = CampagneInnovation.Statut.ACTIVE
        camp.tag_auto = 'Pompage'
        camp.save(update_fields=['statut', 'tag_auto'])
        services.log_campagne_changes(camp, anciennes, self.admin)

        entries = chatter_qs(camp, company=self.co_a)
        fields = {e.field for e in entries}
        self.assertIn('statut', fields)
        self.assertIn('tag_auto', fields)
        self.assertNotIn('segment', fields)
        self.assertNotIn('message_incitation', fields)

    def test_no_change_logs_nothing(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Sans changement')
        anciennes = {
            champ: getattr(camp, champ) for champ in services.CAMPAGNE_CHAMPS_SUIVIS
        }
        services.log_campagne_changes(camp, anciennes, self.admin)
        self.assertEqual(chatter_qs(camp, company=self.co_a).count(), 0)


class CampagneChatterApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide33-api-a', 'A')
        self.admin = make_user(self.co_a, 'ntide33-api-admin')
        self.camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage')

    def test_create_logs_creation(self):
        resp = auth(self.admin).post(
            '/api/django/innovation/campagnes/', {'nom': 'Nouvelle'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        camp = CampagneInnovation.objects.get(pk=resp.data['id'])
        entries = chatter_qs(camp, company=self.co_a)
        self.assertTrue(entries.filter(kind=Activity.Kind.CREATION).exists())

    def test_patch_logs_field_change(self):
        resp = auth(self.admin).patch(
            f'/api/django/innovation/campagnes/{self.camp.id}/',
            {'tag_auto': 'Solaire'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entries = chatter_qs(self.camp, company=self.co_a)
        self.assertTrue(entries.filter(field='tag_auto').exists())

    def test_historique_endpoint_returns_chatter(self):
        services.log_campagne_creation(self.camp, self.admin)
        resp = auth(self.admin).get(
            f'/api/django/innovation/campagnes/{self.camp.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_noter_endpoint_adds_manual_note(self):
        resp = auth(self.admin).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/noter/',
            {'body': 'Prioriser cette campagne.'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        entries = chatter_qs(self.camp, company=self.co_a)
        self.assertTrue(
            entries.filter(kind=Activity.Kind.NOTE,
                           body='Prioriser cette campagne.').exists())

    def test_noter_requires_body(self):
        resp = auth(self.admin).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/noter/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_detail_serializer_includes_historique(self):
        services.log_campagne_creation(self.camp, self.admin)
        resp = auth(self.admin).get(
            f'/api/django/innovation/campagnes/{self.camp.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('historique', resp.data)
        self.assertGreaterEqual(len(resp.data['historique']), 1)

    def test_clone_logs_creation(self):
        resp = auth(self.admin).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.assertEqual(resp.status_code, 201, resp.data)
        clone = CampagneInnovation.objects.get(pk=resp.data['id'])
        entries = chatter_qs(clone, company=self.co_a)
        self.assertTrue(entries.filter(kind=Activity.Kind.CREATION).exists())
