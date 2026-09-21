"""Tests de la modération de contenu (NTIDE19 — « masquer » sans supprimer).

Couvre : réservé au palier Directeur/Responsable, l'idée masquée disparaît
des listes normales pour TOUS (y compris son auteur) mais reste consultable
via ``?include_archived=1`` réservé au même palier, jamais supprimée,
chatter journalisé, isolation multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ModerationIdeeTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-mod-a', 'A')
        self.co_b = make_company('innov-mod-b', 'B')
        self.author = make_user(self.co_a, 'innov-mod-author')
        self.normal_a = make_user(self.co_a, 'innov-mod-normal')
        self.resp_a = make_user(self.co_a, 'innov-mod-resp', role='responsable')
        self.user_b = make_user(self.co_b, 'innov-mod-b-user')
        self.idee = Idee.objects.create(
            company=self.co_a, titre='Idée problématique', auteur=self.author)

    def test_masquer_sets_archived_true(self):
        resp = auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/masquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.idee.refresh_from_db()
        self.assertTrue(self.idee.archived)

    def test_masquer_refused_for_normal_role(self):
        resp = auth(self.normal_a).post(f'{self.BASE}{self.idee.id}/masquer/')
        self.assertEqual(resp.status_code, 403)
        self.idee.refresh_from_db()
        self.assertFalse(self.idee.archived)

    def test_masquee_hidden_from_normal_list_for_everyone(self):
        self.idee.archived = True
        self.idee.save(update_fields=['archived'])
        # Même l'auteur ne la voit plus dans la liste normale.
        resp_author = auth(self.author).get(self.BASE)
        self.assertEqual(len(rows(resp_author)), 0)
        resp_resp = auth(self.resp_a).get(self.BASE)
        self.assertEqual(len(rows(resp_resp)), 0)

    def test_masquee_visible_with_include_archived_for_responsable(self):
        self.idee.archived = True
        self.idee.save(update_fields=['archived'])
        resp = auth(self.resp_a).get(self.BASE, {'include_archived': '1'})
        self.assertEqual(len(rows(resp)), 1)

    def test_include_archived_ignored_for_normal_role(self):
        self.idee.archived = True
        self.idee.save(update_fields=['archived'])
        resp = auth(self.normal_a).get(self.BASE, {'include_archived': '1'})
        self.assertEqual(len(rows(resp)), 0)

    def test_masquer_does_not_delete(self):
        auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/masquer/')
        self.assertTrue(Idee.objects.filter(id=self.idee.id).exists())

    def test_masquer_logs_chatter(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        auth(self.resp_a).post(f'{self.BASE}{self.idee.id}/masquer/')
        ct = ContentType.objects.get_for_model(Idee)
        act = Activity.objects.get(
            content_type=ct, object_id=self.idee.id, field='archived')
        self.assertEqual(act.new_value, 'True')
        self.assertEqual(act.created_by, self.resp_a)

    def test_masquer_cross_tenant_404(self):
        resp = auth(self.user_b).post(f'{self.BASE}{self.idee.id}/masquer/')
        self.assertEqual(resp.status_code, 404)

    def test_masquee_excluded_from_dashboard(self):
        self.idee.archived = True
        self.idee.save(update_fields=['archived'])
        Idee.objects.create(company=self.co_a, titre='Publiée normale')
        resp = auth(self.resp_a).get(f'{self.BASE}tableau-bord/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['par_statut']['total'], 1)
