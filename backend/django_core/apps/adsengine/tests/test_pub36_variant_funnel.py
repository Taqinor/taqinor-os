"""PUB36 — Entonnoir de décrochage par étape, PAR VARIANTE (ad).

Prouve : comptes cumulatifs « a atteint au moins l'étape X » PAR AD (mêmes
garanties que ``reporting.campaign_funnel`` §5.2, résolues par ad plutôt que
par campagne) ; COLD/perdu comptés À CÔTÉ (jamais dans l'entonnoir) ; leads
sans variante résolue en bucket « non résolu » (jamais fondus dans
organique) ; organique exclu du dénominateur ; gating de l'endpoint.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead
from apps.crm.stages import COLD, CONTACTED, NEW, QUOTE_SENT, SIGNED
from apps.roles.models import Role

from apps.adsengine import attribution, reporting
from apps.adsengine.models import AdCampaignMirror, AdMirror, AdSetMirror

User = get_user_model()


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


class VariantStageFunnelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Funnel Co', slug='funnel-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_pub36', name='Campagne',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_pub36', name='Toit',
            campaign=self.camp)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_pub36', name='Ad Funnel',
            adset=self.adset)

    def _lead(self, stage, **kw):
        kw.setdefault('meta_ad_id', 'ad_pub36')
        kw.setdefault('canal', Lead.Canal.META_ADS)
        return Lead.objects.create(company=self.company, nom='P', stage=stage, **kw)

    def test_cumulative_reach_per_ad_cold_and_perdu_aside(self):
        for _ in range(3):
            self._lead(NEW)
        for _ in range(2):
            self._lead(QUOTE_SENT)
        self._lead(SIGNED)
        self._lead(COLD)
        self._lead(CONTACTED, perdu=True)

        res = attribution.variant_stage_funnel(self.company)
        self.assertEqual(len(res['variants']), 1)
        v = res['variants'][0]
        self.assertEqual(v['meta_id'], 'ad_pub36')
        self.assertEqual(v['total'], 8)
        self.assertEqual(v['cold'], 1)
        self.assertEqual(v['perdu'], 1)
        reached = {b['stage']: b['reached'] for b in v['funnel']}
        self.assertEqual(reached[NEW], 6)
        self.assertEqual(reached[CONTACTED], 3)
        self.assertEqual(reached[QUOTE_SENT], 3)
        self.assertEqual(reached[SIGNED], 1)

    def test_stages_come_from_pipeline_stage_order_never_hardcoded(self):
        """Grep-garde : le module ne code jamais littéralement les clés
        d'étape (elles viennent de ``pipeline_stage_order()``)."""
        import inspect
        src = inspect.getsource(attribution.variant_stage_funnel)
        for literal in ('"NEW"', "'NEW'", '"SIGNED"', "'SIGNED'"):
            self.assertNotIn(literal, src)

    def test_unresolved_bucket_never_merged_into_organic(self):
        self._lead(SIGNED, meta_ad_id='', canal=Lead.Canal.WHATSAPP_CTWA)
        res = attribution.variant_stage_funnel(self.company)
        self.assertEqual(res['unresolved']['total'], 1)
        self.assertEqual(res['organic_excluded_count'], 0)
        reached = {b['stage']: b['reached'] for b in res['unresolved']['funnel']}
        self.assertEqual(reached[SIGNED], 1)

    def test_organic_excluded_from_denominator(self):
        Lead.objects.create(
            company=self.company, nom='Organique', stage=SIGNED,
            canal=Lead.Canal.TELEPHONE)
        res = attribution.variant_stage_funnel(self.company)
        self.assertEqual(res['organic_excluded_count'], 1)
        self.assertEqual(res['variants'][0]['total'], 0)

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other', slug='other-pub36')
        Lead.objects.create(
            company=other, nom='X', stage=SIGNED, meta_ad_id='ad_pub36',
            canal=Lead.Canal.META_ADS)
        self._lead(SIGNED)
        res = attribution.variant_stage_funnel(self.company)
        self.assertEqual(res['variants'][0]['total'], 1)


class ReportingVariantFunnelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Rep Funnel', slug='rep-funnel')
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_r36', name='Campagne',
            status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_r36', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=self.company, meta_id='ad_r36', name='Ad Report',
            adset=adset)

    def test_reporting_wrapper_matches_attribution(self):
        Lead.objects.create(
            company=self.company, nom='P', stage=NEW, meta_ad_id='ad_r36',
            canal=Lead.Canal.META_ADS)
        direct = attribution.variant_stage_funnel(self.company)
        wrapped = reporting.variant_funnel(self.company)
        self.assertEqual(direct, wrapped)

    def test_endpoint_returns_funnel(self):
        viewer = make_user(self.company, 'viewer36', ['adsengine_view'])
        Lead.objects.create(
            company=self.company, nom='P', stage=NEW, meta_ad_id='ad_r36',
            canal=Lead.Canal.META_ADS)
        resp = auth(viewer).get(
            '/api/django/adsengine/reporting/entonnoir-variantes/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('variants', resp.json())

    def test_endpoint_gated(self):
        nobody = make_user(self.company, 'nobody36', [])
        url = '/api/django/adsengine/reporting/entonnoir-variantes/'
        self.assertEqual(auth(nobody).get(url).status_code, 403)
