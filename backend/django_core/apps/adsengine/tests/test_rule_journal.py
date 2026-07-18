"""ADSDEEP43 — Journal d'exécution ENRICHI : le « pourquoi » de chaque passe.

Prouve : ``last_result`` porte, par entité, le verdict de condition avec ses
VALEURS (``condition_fr``) et le DELTA de l'action proposée (``action``) ; et
l'endpoint ``regles/journal/`` rend ce journal (permission ``adsengine_view``).
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, InsightSnapshot, RulePolicy,
)

User = get_user_model()
JOURNAL_URL = '/api/django/adsengine/regles/journal/'
TODAY = datetime.date(2026, 7, 16)


def _make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _snap(company, obj, *, day, spend, results):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results)


class EnrichedLastResultTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='JN Co', slug='jn-co')

    def test_stop_loss_run_records_condition_and_pause_delta(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        for d in range(5):
            _snap(self.company, camp, day=d, spend=300, results=1)
        policy = RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        policy.refresh_from_db()
        findings = policy.last_result['findings']
        self.assertEqual(len(findings), 1)
        f = findings[0]
        # Verdict de condition AVEC ses valeurs (jamais un simple booléen).
        self.assertIn('condition_fr', f)
        self.assertIn('vrai', f['condition_fr'])
        self.assertIn('250', f['condition_fr'])  # le seuil comparé
        # Delta de l'action proposée : pause de la cible.
        self.assertEqual(f['action']['kind'], EngineAction.Kind.PAUSE)
        self.assertEqual(f['action']['delta']['type'], 'pause')
        self.assertEqual(f['action']['delta']['target'], 'c1')

    def test_surf_scale_run_records_budget_delta(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='WIN', status='ACTIVE',
            budget='10000')  # 100 MAD (centimes)
        for d in (0, 1, 2):
            _snap(self.company, adset, day=d, spend=10, results=10)
        for d in (3, 4, 5, 6):
            _snap(self.company, adset, day=d, spend=30, results=5)
        policy = RulePolicy.objects.create(
            company=self.company, template_key='surf_scale_budget', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        policy.refresh_from_db()
        f = policy.last_result['findings'][0]
        self.assertIn('condition_fr', f)
        delta = f['action']['delta']
        self.assertEqual(delta['type'], 'budget')
        self.assertEqual(delta['current_mad'], 100.0)
        self.assertLessEqual(delta['new_mad'], 120.0)  # cap ≤ 20 %
        self.assertGreater(delta['new_mad'], 100.0)


class JournalEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='JE Co', slug='je-co')
        self.viewer = _make_user(self.company, 'viewer', ['adsengine_view'])
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        for d in range(5):
            _snap(self.company, camp, day=d, spend=300, results=1)
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)

    def test_journal_returns_enriched_run(self):
        resp = _auth(self.viewer).get(JOURNAL_URL)
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results']
        entry = next(r for r in results if r['template_key'] == 'stop_loss_cpl')
        self.assertTrue(entry['fired'])
        f = entry['findings'][0]
        self.assertIn('condition_fr', f)
        self.assertEqual(f['action']['delta']['type'], 'pause')

    def test_journal_requires_view_permission(self):
        nobody = _make_user(self.company, 'nobody', [])
        resp = _auth(nobody).get(JOURNAL_URL)
        self.assertEqual(resp.status_code, 403)
