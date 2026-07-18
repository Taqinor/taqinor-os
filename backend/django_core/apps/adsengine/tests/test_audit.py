"""ADSDEEP63 — Tests de l'audit de compte à la demande (Madgicx-style, FR).

Prouve : chaque section calcule un chiffre RÉEL depuis les fixtures (jamais un
score opaque), dégrade proprement sans donnée (statut 'inconnu', jamais une
exception), et l'endpoint est gaté ``adsengine_view``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import audit
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror,
    InsightSnapshot, MetaConnection,
)

User = get_user_model()
AUDIT_URL = '/api/django/adsengine/reporting/audit/'


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


class AuditNamingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Audit Co', slug='audit-co')

    def test_no_ads_gives_unknown(self):
        section = audit._audit_naming(self.company)
        self.assertEqual(section['statut'], 'inconnu')

    def test_mostly_untagged_flags_attention(self):
        AdMirror.objects.create(
            company=self.company, meta_id='a1', name='a1')
        AdMirror.objects.create(
            company=self.company, meta_id='a2', name='a2')
        AdMirror.objects.create(
            company=self.company, meta_id='a3', name='UGC_PAIN_ROI',
            hook_tag='PAIN', angle_tag='ROI', format_tag='UGC')
        section = audit._audit_naming(self.company)
        self.assertEqual(section['statut'], 'attention')
        self.assertIn('2/3', section['items'][0])

    def test_all_tagged_is_ok(self):
        AdMirror.objects.create(
            company=self.company, meta_id='a1', name='a1',
            hook_tag='PAIN', angle_tag='ROI', format_tag='UGC')
        section = audit._audit_naming(self.company)
        self.assertEqual(section['statut'], 'ok')
        self.assertEqual(section['items'], [])


class AuditFragmentationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Frag Co', slug='frag-co')

    def test_no_campaigns_gives_unknown(self):
        section = audit._audit_budget_fragmentation(self.company)
        self.assertEqual(section['statut'], 'inconnu')

    def test_fragmented_campaign_flagged(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp Frag')
        for i in range(3):
            AdSetMirror.objects.create(
                company=self.company, meta_id=f'as{i}', campaign=camp,
                learning_status=AdSetMirror.LearningStatus.LEARNING)
        section = audit._audit_budget_fragmentation(self.company)
        self.assertEqual(section['statut'], 'attention')
        self.assertIn('Camp Frag', section['items'][0])

    def test_few_adsets_never_flagged(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp Small')
        AdSetMirror.objects.create(
            company=self.company, meta_id='as0', campaign=camp,
            learning_status=AdSetMirror.LearningStatus.LEARNING)
        section = audit._audit_budget_fragmentation(self.company)
        self.assertEqual(section['statut'], 'ok')

    def test_many_adsets_but_learned_never_flagged(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp OK')
        for i in range(3):
            AdSetMirror.objects.create(
                company=self.company, meta_id=f'as{i}', campaign=camp,
                learning_status=AdSetMirror.LearningStatus.SUCCESS)
        section = audit._audit_budget_fragmentation(self.company)
        self.assertEqual(section['statut'], 'ok')


class AuditFatigueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Fatigue Co', slug='fatigue-co')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def test_high_frequency_flags_attention(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp Fatigue')
        day = datetime.date(2026, 7, 16)
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=camp.pk,
            date=day, spend='100.00', results=5, frequency='3.00')
        section = audit._audit_fatigue(self.company, now=day)
        self.assertEqual(section['statut'], 'attention')
        self.assertIn('Camp Fatigue', section['items'][0])

    def test_low_frequency_is_ok(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp Sain')
        day = datetime.date(2026, 7, 16)
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=camp.pk,
            date=day, spend='100.00', results=5, frequency='1.20')
        section = audit._audit_fatigue(self.company, now=day)
        self.assertEqual(section['statut'], 'ok')


class AuditTrackingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Track Co', slug='track-co')

    def test_no_pixel_no_capi_flags_attention(self):
        section = audit._audit_tracking(self.company)
        self.assertEqual(section['statut'], 'attention')
        self.assertTrue(any('pixel' in item.lower() for item in section['items']))
        self.assertTrue(any('capi' in item.lower() for item in section['items']))

    def test_pixel_configured_removes_pixel_item(self):
        MetaConnection.objects.create(
            company=self.company, pixel_id='123456')
        section = audit._audit_tracking(self.company)
        self.assertFalse(
            any('pixel' in item.lower() for item in section['items']))

    def test_link_without_utm_flagged(self):
        ad = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='a1')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad,
            link_url='https://example.com/landing')
        section = audit._audit_tracking(self.company)
        self.assertTrue(any('UTM' in item for item in section['items']))

    def test_link_with_utm_not_flagged(self):
        ad = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='a1')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad,
            link_url='https://example.com/landing?utm_source=meta')
        section = audit._audit_tracking(self.company)
        self.assertFalse(any('UTM' in item for item in section['items']))


class AuditDataWindowsTests(TestCase):
    def test_always_returns_five_messages(self):
        section = audit._audit_data_windows()
        self.assertEqual(section['statut'], 'info')
        self.assertEqual(len(section['items']), 5)


class RunAccountAuditTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Full Audit Co', slug='full-audit-co')

    def test_returns_all_sections(self):
        data = audit.run_account_audit(self.company, now=datetime.date(2026, 7, 16))
        self.assertIn('genere_le', data)
        sections = data['sections']
        for key in ('naming', 'fragmentation_budgetaire', 'fatigue',
                    'tracking', 'fenetres_donnees'):
            self.assertIn(key, sections)
            self.assertIn('lien', sections[key])


class AccountAuditEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='EP Audit Co', slug='ep-audit-co')
        self.viewer = make_user(self.company, 'auditviewer', ['adsengine_view'])

    def test_endpoint_returns_data(self):
        resp = auth(self.viewer).get(AUDIT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('sections', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'auditnobody', [])
        self.assertEqual(auth(nobody).get(AUDIT_URL).status_code, 403)

    def test_company_scoped(self):
        other = Company.objects.create(nom='Other Co', slug='other-co-audit')
        AdMirror.objects.create(
            company=other, meta_id='x1', name='x1',
            hook_tag='H', angle_tag='A', format_tag='F')
        resp = auth(self.viewer).get(AUDIT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        # La société du viewer n'a aucune ad : jamais celles d'une autre société.
        self.assertEqual(
            resp.data['sections']['naming']['statut'], 'inconnu')
