"""AANA17 (C-AANA-007, volet vues) — un responsable de A ne peut pas poser un
rôle de B sur une vue, ni par l'écriture directe ni par l'action
``definir-par-defaut-role``.

Scénario U4. Avant le correctif : 200 et ``role_id`` = rôle de B.

Données RÉELLES en base (aucun mock). Retirer ``same_company_fields`` (ou
le contrôle de l'action) rougit ce test.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from authentication.models import Company

from .models import SavedView

User = get_user_model()

BASE = '/api/django/uxviews/saved-views/'


class TestRoleSociete(TestCase):
    def setUp(self):
        self.co_a = Company.objects.get_or_create(
            slug='aana17-a', defaults={'nom': 'AANA17 A'})[0]
        self.co_b = Company.objects.get_or_create(
            slug='aana17-b', defaults={'nom': 'AANA17 B'})[0]
        self.responsable = User.objects.create_user(
            username='aana17_resp', password='x', company=self.co_a,
            role_legacy='responsable')
        self.role_a = Role.objects.create(
            company=self.co_a, nom='Commercial A', permissions=[])
        self.role_b = Role.objects.create(
            company=self.co_b, nom='Commercial B', permissions=[])
        self.vue = SavedView.objects.create(
            company=self.co_a, owner=self.responsable, ecran='crm.leads',
            nom='Ma vue')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.responsable)}'))

    def test_role_autre_societe_refuse(self):
        resp = self.api.post(
            f'{BASE}{self.vue.pk}/definir-par-defaut-role/',
            {'role': self.role_b.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('role', resp.data)
        self.vue.refresh_from_db()
        self.assertIsNone(self.vue.role_id)
        self.assertFalse(self.vue.est_defaut_role)

        # Écriture directe du champ : même refus.
        resp = self.api.patch(f'{BASE}{self.vue.pk}/',
                              {'role': self.role_b.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.vue.refresh_from_db()
        self.assertIsNone(self.vue.role_id)

    def test_role_meme_societe_accepte(self):
        resp = self.api.post(
            f'{BASE}{self.vue.pk}/definir-par-defaut-role/',
            {'role': self.role_a.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.vue.refresh_from_db()
        self.assertEqual(self.vue.role_id, self.role_a.pk)
