"""ADSDEEP25 — Tests des conversations WhatsApp RÉELLES par ad (CtwaReferral)
+ jointure signatures par téléphone + endpoint (company-scopé, permission).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.crm import stages
from apps.crm.models import Lead
from apps.adsengine.metrics import conversations_per_ad
from apps.adsengine.models import CtwaReferral

User = get_user_model()
URL = '/api/django/adsengine/metrics/conversations-per-ad/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ConversationsPerAdTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CV Co', slug='cv')

    def _ref(self, wa_id, ad_id, phone):
        from apps.crm.services import normalize_phone
        CtwaReferral.objects.create(
            company=self.company, wa_message_id=wa_id, ad_id=ad_id,
            phone_key=normalize_phone(phone))

    def test_counts_conversations_and_signed(self):
        # Ad A : deux conversations, deux contacts distincts, un signé.
        self._ref('w1', 'adA', '0600000001')
        self._ref('w2', 'adA', '0600000002')
        # Ad B : une conversation, non signé.
        self._ref('w3', 'adB', '0600000003')
        # Lead SIGNÉ dont le téléphone == contact 1 de adA.
        Lead.objects.create(
            company=self.company, nom='Signé', telephone='+212600000001',
            stage=stages.SIGNED)

        result = conversations_per_ad(self.company)
        by_ad = {r['ad_id']: r for r in result['by_ad']}
        self.assertEqual(by_ad['adA']['conversations'], 2)
        self.assertEqual(by_ad['adA']['unique_contacts'], 2)
        self.assertEqual(by_ad['adA']['signed'], 1)
        self.assertEqual(by_ad['adB']['conversations'], 1)
        self.assertEqual(by_ad['adB']['signed'], 0)
        self.assertEqual(result['total_conversations'], 3)
        self.assertEqual(result['total_signed'], 1)

    def test_referrals_without_ad_id_excluded(self):
        self._ref('w9', '', '0600000009')
        result = conversations_per_ad(self.company)
        self.assertEqual(result['by_ad'], [])
        self.assertEqual(result['total_conversations'], 0)

    def test_endpoint_ok_and_isolated(self):
        self._ref('w1', 'adA', '0600000001')
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        resp = auth(viewer).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_conversations'], 1)

        other = Company.objects.create(nom='CV B', slug='cvb')
        other_viewer = make_user(other, 'ov', ['adsengine_view'])
        resp2 = auth(other_viewer).get(URL)
        self.assertEqual(resp2.data['total_conversations'], 0)

    def test_requires_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(auth(nobody).get(URL).status_code, 403)
