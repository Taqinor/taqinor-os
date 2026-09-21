"""Tests de la modération du feedback produit (NTIDE47 — « masquer » sans
supprimer, palier Directeur STRICT).

Couvre : réservé au palier Directeur/Administrateur (jamais Responsable,
contrairement à ``IdeasModerate`` sur les idées), le feedback masqué
disparaît des listes admin normales mais reste consultable via
``?include_archived=1`` réservé au même palier, jamais supprimé, chatter
journalisé, exclu des agrégats (feedback_by_theme/hotspot)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class FeedbackModerationTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide47-a', 'A')
        self.admin = make_user(self.co_a, 'ntide47-admin', role_legacy='admin')
        self.resp_a = make_user(self.co_a, 'ntide47-resp', role_legacy='responsable')
        self.normal = make_user(self.co_a, 'ntide47-normal')
        self.fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Retour inapproprié')

    def test_admin_can_masquer(self):
        resp = auth(self.admin).post(f'{self.BASE}{self.fb.id}/masquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.fb.refresh_from_db()
        self.assertTrue(self.fb.archived)

    def test_responsable_refused(self):
        """Directeur STRICT — Responsable n'y a PAS accès (contrairement à
        IdeasModerate sur les idées)."""
        resp = auth(self.resp_a).post(f'{self.BASE}{self.fb.id}/masquer/')
        self.assertEqual(resp.status_code, 403)
        self.fb.refresh_from_db()
        self.assertFalse(self.fb.archived)

    def test_normal_refused(self):
        resp = auth(self.normal).post(f'{self.BASE}{self.fb.id}/masquer/')
        self.assertEqual(resp.status_code, 403)

    def test_masque_hidden_from_admin_list(self):
        self.fb.archived = True
        self.fb.save(update_fields=['archived'])
        resp = auth(self.admin).get(self.BASE)
        self.assertEqual(len(rows(resp)), 0)

    def test_masque_visible_with_include_archived_for_admin(self):
        self.fb.archived = True
        self.fb.save(update_fields=['archived'])
        resp = auth(self.admin).get(self.BASE, {'include_archived': '1'})
        self.assertEqual(len(rows(resp)), 1)

    def test_include_archived_ignored_for_responsable(self):
        self.fb.archived = True
        self.fb.save(update_fields=['archived'])
        resp = auth(self.resp_a).get(self.BASE, {'include_archived': '1'})
        self.assertEqual(len(rows(resp)), 0)

    def test_masquer_does_not_delete(self):
        auth(self.admin).post(f'{self.BASE}{self.fb.id}/masquer/')
        self.assertTrue(FeedbackProduit.objects.filter(id=self.fb.id).exists())

    def test_masquer_logs_chatter(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        auth(self.admin).post(f'{self.BASE}{self.fb.id}/masquer/')
        ct = ContentType.objects.get_for_model(FeedbackProduit)
        act = Activity.objects.get(
            content_type=ct, object_id=self.fb.id, field='archived')
        self.assertEqual(act.new_value, 'True')
        self.assertEqual(act.created_by, self.admin)

    def test_masque_excluded_from_theme_aggregate(self):
        self.fb.archived = True
        self.fb.save(update_fields=['archived'])
        resume = selectors.feedback_by_theme(self.co_a)
        self.assertEqual(resume, [])

    def test_masque_excluded_from_hotspot(self):
        for _ in range(10):
            FeedbackProduit.objects.create(
                company=self.co_a, auteur=self.normal, titre='Retour',
                source_page='/crm/leads', archived=True)
        self.assertEqual(selectors.hotspot_feedback(self.co_a), [])
