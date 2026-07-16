"""ADSENG1 — Tests du correctif d'attribution Lead Ads.

Prouve :
  * ``resolve_meta_ad_names`` résout les noms via les miroirs ENG5 (ad → ad set
    → campagne), avec repli paresseux API quand les miroirs manquent ;
  * ``create_lead_from_meta_lead_ads`` capture ad_id/adgroup_id/form_id, remplit
    ``utm_content = ad-<ad_id>`` et ``utm_campaign`` = nom résolu (un lead
    Testing-Tool-shaped porte donc une attribution par variante réelle) ;
  * la commande/service de backfill est idempotente et best-effort.

Aucune de ces vérifications n'atteint un vrai serveur Meta (fetch simulé).
"""
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.services import (
    backfill_meta_lead_attribution, create_lead_from_meta_lead_ads,
)
from apps.adsengine import selectors
from apps.adsengine.models import AdCampaignMirror, AdMirror, AdSetMirror


class ResolveMetaAdNamesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Res Co', slug='res-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_701', name='Solaire Casa',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_702', name='Toit Résidentiel',
            campaign=self.camp)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_703', name='Reel A',
            adset=self.adset)

    def test_resolves_full_lineage_from_mirrors(self):
        names = selectors.resolve_meta_ad_names(
            self.company, ad_id='ad_703', adgroup_id='ast_702')
        self.assertEqual(names['campaign_name'], 'Solaire Casa')
        self.assertEqual(names['adset_name'], 'Toit Résidentiel')
        self.assertEqual(names['campaign_id'], 'cmp_701')

    def test_resolves_via_adgroup_when_ad_mirror_absent(self):
        names = selectors.resolve_meta_ad_names(
            self.company, ad_id='ad_UNKNOWN', adgroup_id='ast_702')
        self.assertEqual(names['campaign_name'], 'Solaire Casa')
        self.assertEqual(names['adset_name'], 'Toit Résidentiel')

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other', slug='other-res')
        names = selectors.resolve_meta_ad_names(
            other, ad_id='ad_703', adgroup_id='ast_702')
        self.assertEqual(names['campaign_name'], '')
        self.assertEqual(names['adset_name'], '')

    def test_lazy_api_fallback_when_no_mirror(self):
        empty = Company.objects.create(nom='NoMirror', slug='no-mirror')
        payload = {
            'name': 'Reel Z',
            'adset': {'id': 'ast_900', 'name': 'AdSet API'},
            'campaign': {'id': 'cmp_900', 'name': 'Campagne API'},
        }
        with patch.object(selectors, '_fetch_ad_lineage', return_value=payload):
            names = selectors.resolve_meta_ad_names(
                empty, ad_id='ad_900', access_token='tok')
        self.assertEqual(names['campaign_name'], 'Campagne API')
        self.assertEqual(names['adset_name'], 'AdSet API')
        self.assertEqual(names['campaign_id'], 'cmp_900')

    def test_no_token_no_mirror_returns_empty(self):
        empty = Company.objects.create(nom='NoTok', slug='no-tok')
        names = selectors.resolve_meta_ad_names(empty, ad_id='ad_x')
        self.assertEqual(
            names, {'campaign_name': '', 'adset_name': '', 'campaign_id': ''})


class CreateLeadFromMetaLeadAdsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Lead Co', slug='lead-co')
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_11', name='Pompage Sud',
            status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_22', name='Agriculteurs',
            campaign=camp)
        AdMirror.objects.create(
            company=self.company, meta_id='ad_33', name='Static A',
            adset=adset)

    def _field_data(self):
        return [
            {'name': 'full_name', 'values': ['Ahmed Test']},
            {'name': 'phone_number', 'values': ['+212600112233']},
        ]

    def test_testing_tool_lead_carries_variant_attribution(self):
        lead = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='lg_5551',
            field_data=self._field_data(),
            ad_id='ad_33', adgroup_id='ast_22', form_id='frm_44')
        lead.refresh_from_db()
        self.assertEqual(lead.meta_ad_id, 'ad_33')
        self.assertEqual(lead.meta_adset_id, 'ast_22')
        self.assertEqual(lead.meta_campaign_id, 'cmp_11')
        self.assertEqual(lead.meta_form_id, 'frm_44')
        # utm_content = ad-<ad_id> (convention ADSENG23), jamais l'adset_name.
        self.assertEqual(lead.utm_content, 'ad-ad_33')
        self.assertEqual(lead.utm_campaign, 'Pompage Sud')
        self.assertEqual(lead.utm_source, 'facebook')
        self.assertEqual(lead.canal, Lead.Canal.META_ADS)

    def test_lead_without_ad_id_has_no_variant(self):
        lead = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='lg_5552',
            field_data=self._field_data())
        lead.refresh_from_db()
        self.assertIsNone(lead.meta_ad_id)
        self.assertIsNone(lead.utm_content)
        self.assertEqual(lead.utm_source, 'facebook')

    def test_idempotent_on_repeated_leadgen_id(self):
        first = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='lg_5553',
            field_data=self._field_data(), ad_id='ad_33', adgroup_id='ast_22')
        again = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='lg_5553',
            field_data=self._field_data(), ad_id='ad_33', adgroup_id='ast_22')
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)


class BackfillMetaLeadAttributionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BF Co', slug='bf-co')
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_88', name='Rétro Campagne',
            status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_77', name='Rétro AdSet',
            campaign=camp)
        AdMirror.objects.create(
            company=self.company, meta_id='ad_66', name='Rétro Ad',
            adset=adset)
        # Lead Lead Ads EXISTANT sans identifiants natifs (créé avant ADSENG1).
        self.legacy = Lead.objects.create(
            company=self.company, nom='Vieux Lead',
            source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
            utm_source='facebook',
            external_system='meta_lead_ads', external_id='lg_old_1')

    def test_backfill_fills_variant_attribution(self):
        node = {'ad_id': 'ad_66', 'adgroup_id': 'ast_77', 'form_id': 'frm_99'}

        def fake_fetch(leadgen_id, access_token):
            self.assertEqual(leadgen_id, 'lg_old_1')
            return node

        stats = backfill_meta_lead_attribution(
            company=self.company, access_token='tok', fetch_fn=fake_fetch)
        self.assertEqual(stats['updated'], 1)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.meta_ad_id, 'ad_66')
        self.assertEqual(self.legacy.meta_adset_id, 'ast_77')
        self.assertEqual(self.legacy.meta_campaign_id, 'cmp_88')
        self.assertEqual(self.legacy.utm_content, 'ad-ad_66')
        self.assertEqual(self.legacy.utm_campaign, 'Rétro Campagne')

    def test_backfill_is_idempotent(self):
        node = {'ad_id': 'ad_66', 'adgroup_id': 'ast_77'}

        def fake_fetch(leadgen_id, access_token):
            return node

        first = backfill_meta_lead_attribution(
            company=self.company, access_token='tok', fetch_fn=fake_fetch)
        second = backfill_meta_lead_attribution(
            company=self.company, access_token='tok', fetch_fn=fake_fetch)
        self.assertEqual(first['updated'], 1)
        # Le lead déjà backfillé (meta_ad_id posé) n'est plus scanné.
        self.assertEqual(second['scanned'], 0)
        self.assertEqual(second['updated'], 0)

    def test_backfill_fetch_failure_is_best_effort(self):
        def boom(leadgen_id, access_token):
            raise RuntimeError('réseau HS')

        stats = backfill_meta_lead_attribution(
            company=self.company, access_token='tok', fetch_fn=boom)
        self.assertEqual(stats['failed'], 1)
        self.assertEqual(stats['updated'], 0)
        self.legacy.refresh_from_db()
        self.assertIsNone(self.legacy.meta_ad_id)
