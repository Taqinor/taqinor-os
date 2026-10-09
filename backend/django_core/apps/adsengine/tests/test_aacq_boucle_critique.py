"""AACQ24 — La boucle CRITIQUE évalue vraiment « Zéro diffusion malgré dépense »,
et un gabarit sans évaluateur n'est plus armable (400).
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rule_templates, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, EngineAlert, InsightSnapshot, RulePolicy,
)

User = get_user_model()
# Gabarits du catalogue DÉLIBÉRÉMENT non branchés (alertes à venir) : ni
# évaluateur, ni armement possible.
NON_BRANCHES = {'revive', 'budget_pacing_breach', 'low_backlog',
                'recon_divergence'}


class BoucleCritiqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Crit', slug='aacq24-crit')

    def test_zero_delivery_evalue(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-zero', name='Zéro diffusion',
            status='ACTIVE')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        today = timezone.now().date()
        for d in (0, 1):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=camp.pk,
                date=today - datetime.timedelta(days=d), spend='80',
                impressions=0)
        policy = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(
            self.company, cadences=rules_engine.CRITICAL_CADENCES,
            now=timezone.now())
        policy.refresh_from_db()
        self.assertTrue(policy.last_result['evaluated'], policy.last_result)
        finding = policy.last_result['findings'][0]
        self.assertTrue(finding['fired'])
        self.assertEqual(finding['target'], 'c-zero')
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company,
            entity_key='zero_delivery:campaign:c-zero').exists())

    def test_gabarit_sans_evaluateur_non_armable(self):
        role = Role.objects.create(
            company=self.company, nom='aacq24-role',
            permissions=['adsengine_view', 'adsengine_manage'])
        user = User.objects.create_user(
            username='aacq24-com', password='x', company=self.company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.post('/api/django/adsengine/regles/',
                        {'template_key': 'revive', 'enabled': True},
                        format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('non armable', str(resp.data['template_key']))
        self.assertFalse(RulePolicy.objects.filter(
            company=self.company, template_key='revive').exists())
        # Désarmé, il reste créable (catalogue / seed).
        resp = api.post('/api/django/adsengine/regles/',
                        {'template_key': 'revive', 'enabled': False},
                        format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_catalogue_complet(self):
        catalogue = set(rule_templates.RULE_TEMPLATES)
        self.assertEqual(catalogue - NON_BRANCHES,
                         set(rules_engine._EVALUATORS))
        self.assertIn('zero_delivery', rules_engine._EVALUATORS)
        for key in NON_BRANCHES:
            self.assertFalse(rules_engine.is_template_wired(key))
