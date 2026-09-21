"""Tests de l'action « Lier à devis/ticket/chantier » (NTIDE14).

Couvre : mise à jour de ``linked_type``/``linked_id`` (opaque string-FK),
validation du type/identifiant, ouverte à TOUT utilisateur connecté (comme la
proposition, NTIDE4/NTIDE8), chatter (ARC8) journalisant l'ancien/nouveau
lien, isolation multi-société.
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


class LierIdeeTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-lier-a', 'A')
        self.co_b = make_company('innov-lier-b', 'B')
        self.user_a = make_user(self.co_a, 'innov-lier-a')
        self.user_b = make_user(self.co_b, 'innov-lier-b')
        self.idee = Idee.objects.create(company=self.co_a, titre='Une idée')

    def test_lier_devis_updates_fields(self):
        resp = auth(self.user_a).post(
            f'{self.BASE}{self.idee.id}/lier/',
            {'linked_type': 'devis', 'linked_id': 42}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.idee.refresh_from_db()
        self.assertEqual(self.idee.linked_type, Idee.LinkedType.DEVIS)
        self.assertEqual(self.idee.linked_id, 42)

    def test_lier_invalid_type_rejected(self):
        resp = auth(self.user_a).post(
            f'{self.BASE}{self.idee.id}/lier/',
            {'linked_type': 'facture', 'linked_id': 1}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_lier_invalid_id_rejected(self):
        resp = auth(self.user_a).post(
            f'{self.BASE}{self.idee.id}/lier/',
            {'linked_type': 'devis', 'linked_id': 'abc'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_lier_logs_chatter(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        auth(self.user_a).post(
            f'{self.BASE}{self.idee.id}/lier/',
            {'linked_type': 'chantier', 'linked_id': 7}, format='json')
        ct = ContentType.objects.get_for_model(Idee)
        act = Activity.objects.get(
            content_type=ct, object_id=self.idee.id, field='linked_type')
        self.assertEqual(act.new_value, 'chantier #7')
        self.assertEqual(act.created_by, self.user_a)

    def test_lier_cross_tenant_404(self):
        resp = auth(self.user_b).post(
            f'{self.BASE}{self.idee.id}/lier/',
            {'linked_type': 'devis', 'linked_id': 1}, format='json')
        self.assertEqual(resp.status_code, 404)
