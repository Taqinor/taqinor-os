"""ADSDEEP19 — Tests des comptes de leads RÉELS par ad/campagne (MetaLeadMirror)
+ endpoint : compte correct (résolution campagne via l'échelle miroir),
isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import sync
from apps.adsengine.metrics import real_lead_counts
from apps.adsengine.models import MetaLeadMirror

User = get_user_model()
URL = '/api/django/adsengine/metrics/real-leads/'


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


class RealLeadCountsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RL Co', slug='rl')
        # Échelle miroir : campagne c1 → adset as1 → ad ad1.
        sync.sync_campaigns(self.company, [{'id': 'c1', 'name': 'Camp'}])
        sync.sync_adsets(
            self.company, [{'id': 'as1', 'campaign_id': 'c1'}])
        sync.sync_ads(self.company, [{'id': 'ad1', 'adset_id': 'as1'}])

    def _mirror(self, leadgen, ad_id, campaign_id=''):
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id=leadgen, ad_id=ad_id,
            campaign_id=campaign_id)

    def test_counts_resolve_campaign_via_mirror_chain(self):
        # Deux leads sur ad1, campaign_id VIDE (webhook) → résolu via l'échelle.
        self._mirror('lg1', 'ad1')
        self._mirror('lg2', 'ad1')
        counts = real_lead_counts(self.company)
        self.assertEqual(counts['total'], 2)
        self.assertEqual(counts['by_ad']['ad1'], 2)
        self.assertEqual(counts['by_campaign']['c1'], 2)

    def test_explicit_campaign_id_counted(self):
        self._mirror('lg3', 'adX', campaign_id='c9')
        counts = real_lead_counts(self.company)
        self.assertEqual(counts['by_campaign']['c9'], 1)

    def test_endpoint_ok_and_isolated(self):
        self._mirror('lg1', 'ad1')
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        resp = auth(viewer).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['by_campaign']['c1'], 1)

        # Autre société : ne voit jamais les leads de la première.
        other = Company.objects.create(nom='RL B', slug='rlb')
        other_viewer = make_user(other, 'ov', ['adsengine_view'])
        resp2 = auth(other_viewer).get(URL)
        self.assertEqual(resp2.data['total'], 0)

    def test_requires_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(auth(nobody).get(URL).status_code, 403)
