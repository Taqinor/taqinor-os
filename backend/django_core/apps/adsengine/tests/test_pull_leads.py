"""ADSDEEP18 — Tests du pull-sync des leads : backfill mocké idempotent ; les
leads webhook et pull CONVERGENT (même leadgen_id → un seul lead CRM, un seul
miroir).
"""
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import MetaConnection, MetaLeadMirror
from apps.adsengine.selectors import resolve_lead_ads_access_token
from apps.adsengine.tasks import pull_ad_leads_for_company
from apps.crm.models import Lead


class PullFakeClient:
    def get_ad_leads(self, ad_id, *, since_unix=None):
        if ad_id == 'ad1':
            return [{
                'id': 'lg-100', 'created_time': '2026-07-16T10:00:00Z',
                'form_id': 'f1', 'ad_id': 'ad1',
                'field_data': [
                    {'name': 'full_name', 'values': ['Sara Alaoui']},
                    {'name': 'phone_number', 'values': ['+212698765432']},
                ],
            }]
        return []

    def get_ad_targeting_ids(self, ad_id):
        return {'adset_id': 'as1', 'campaign_id': 'c1'}


class PullLeadsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PL Co', slug='pl')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        sync.sync_ads(self.company, [{'id': 'ad1'}, {'id': 'ad2'}])

    def test_pull_creates_lead_and_mirror(self):
        n = pull_ad_leads_for_company(self.company, self.conn, PullFakeClient())
        self.assertEqual(n, 1)
        self.assertTrue(Lead.objects.filter(
            company=self.company, external_id='lg-100').exists())
        m = MetaLeadMirror.objects.get(
            company=self.company, leadgen_id='lg-100')
        self.assertEqual(m.ad_id, 'ad1')
        self.assertEqual(m.adset_id, 'as1')
        self.assertEqual(m.campaign_id, 'c1')

    def test_backfill_idempotent(self):
        pull_ad_leads_for_company(self.company, self.conn, PullFakeClient())
        pull_ad_leads_for_company(self.company, self.conn, PullFakeClient())
        self.assertEqual(
            Lead.objects.filter(
                company=self.company, external_id='lg-100').count(), 1)
        self.assertEqual(
            MetaLeadMirror.objects.filter(
                company=self.company, leadgen_id='lg-100').count(), 1)

    def test_webhook_and_pull_converge(self):
        # Simule d'abord la capture webhook (via l'événement domaine)…
        from core.events import meta_lead_captured
        from apps.crm.services import create_lead_from_meta_lead_ads
        lead = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='lg-100',
            field_data=[{'name': 'phone_number',
                         'values': ['+212698765432']}],
            ad_id='ad1', adgroup_id='as1', form_id='f1')
        meta_lead_captured.send(
            sender='test', lead=lead, company=self.company,
            leadgen_id='lg-100', ad_id='ad1', adset_id='as1', campaign_id='c1',
            form_id='f1', created_time=None, is_organic=False)
        # …puis le pull : même leadgen_id → toujours un seul lead + un miroir.
        pull_ad_leads_for_company(self.company, self.conn, PullFakeClient())
        self.assertEqual(
            Lead.objects.filter(
                company=self.company, external_id='lg-100').count(), 1)
        self.assertEqual(
            MetaLeadMirror.objects.filter(
                company=self.company, leadgen_id='lg-100').count(), 1)

    def test_noop_when_client_lacks_method(self):
        class Old:
            pass
        self.assertEqual(
            pull_ad_leads_for_company(self.company, self.conn, Old()), 0)

    def test_pull_works_with_only_connection_token(self):
        """FIXPUB1 — sans env, le pull fonctionne avec le SEUL token de la
        MetaConnection (le client est bâti depuis la connexion) et le token
        résolu pour la résolution des noms est bien celui de la connexion."""
        with override_settings(META_LEAD_ADS_ACCESS_TOKEN=''):
            token, source = resolve_lead_ads_access_token(self.company)
            n = pull_ad_leads_for_company(
                self.company, self.conn, PullFakeClient(), name_token=token)
        self.assertEqual((token, source), ('tok', 'connection'))
        self.assertEqual(n, 1)
        self.assertTrue(Lead.objects.filter(
            company=self.company, external_id='lg-100').exists())


class LeadAdsTokenResolutionTests(TestCase):
    """FIXPUB1 — repli du token Lead Ads : env prioritaire, sinon la
    MetaConnection activée ; jamais le token d'une connexion désactivée."""

    def setUp(self):
        self.company = Company.objects.create(nom='Tok Co', slug='tok')

    def test_connection_token_when_no_env(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'CONN'}, ad_account_id='act_9')
        with override_settings(META_LEAD_ADS_ACCESS_TOKEN=''):
            self.assertEqual(
                resolve_lead_ads_access_token(self.company),
                ('CONN', 'connection'))

    def test_env_token_wins_over_connection(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'CONN'}, ad_account_id='act_9')
        with override_settings(META_LEAD_ADS_ACCESS_TOKEN='ENV'):
            self.assertEqual(
                resolve_lead_ads_access_token(self.company), ('ENV', 'env'))

    def test_no_token_anywhere(self):
        with override_settings(META_LEAD_ADS_ACCESS_TOKEN=''):
            self.assertEqual(
                resolve_lead_ads_access_token(self.company), ('', None))

    def test_disabled_connection_token_is_ignored(self):
        MetaConnection.objects.create(
            company=self.company, enabled=False,
            credentials={'access_token': 'CONN'}, ad_account_id='act_9')
        with override_settings(META_LEAD_ADS_ACCESS_TOKEN=''):
            self.assertEqual(
                resolve_lead_ads_access_token(self.company), ('', None))
