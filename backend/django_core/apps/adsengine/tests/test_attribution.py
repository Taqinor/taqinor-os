"""ADSENG6 — Tests de la jointure d'attribution PAR VARIANTE.

Fixtures multi-cas (dd-attribution §2.4) : Instant-Form (meta_ad_id direct),
site avec utm_content='ad-<id>', fuzzy par nom d'ad, organique exclu, lead
appel/DM (canal Meta sans utm) en bucket non résolu. Vérifie les chiffres exacts
par variante et que le niveau campagne (ENG10) reste inchangé.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.stages import CONTACTED, NEW, SIGNED

from apps.adsengine import attribution, metrics
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, InsightSnapshot,
)


class VariantAttributionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Attr Co', slug='attr-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_1', name='Solaire Casa',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_1', name='Toit',
            campaign=self.camp)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_100', name='Reel Casa',
            adset=self.adset)
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _spend(self, ad, amount, day):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=day, spend=Decimal(amount), results=1)

    def _lead(self, stage=SIGNED, **attribution_fields):
        return Lead.objects.create(
            company=self.company, nom='Prospect', stage=stage,
            **attribution_fields)

    def test_instant_form_lead_exact_variant_numbers(self):
        # 300 MAD de dépense sur ad_100 ; 3 leads attribués (2 signés, 1 contacté).
        self._spend(self.ad, '200.00', datetime.date(2026, 7, 15))
        self._spend(self.ad, '100.00', datetime.date(2026, 7, 16))
        self._lead(stage=SIGNED, meta_ad_id='ad_100', canal=Lead.Canal.META_ADS)
        self._lead(stage=SIGNED, meta_ad_id='ad_100', canal=Lead.Canal.META_ADS)
        self._lead(stage=CONTACTED, meta_ad_id='ad_100',
                   canal=Lead.Canal.META_ADS)

        res = attribution.variant_attribution(self.company)
        self.assertEqual(len(res['variants']), 1)
        v = res['variants'][0]
        self.assertEqual(v['meta_id'], 'ad_100')
        self.assertEqual(v['spend'], '300.00')
        self.assertEqual(v['leads'], 3)
        self.assertEqual(v['qualified'], 3)
        self.assertEqual(v['signed'], 2)
        self.assertEqual(v['cost_per_signature'], '150.00')
        self.assertEqual(v['cost_per_qualified_lead'], '100.00')

    def test_utm_content_ad_convention_resolves(self):
        self._spend(self.ad, '100.00', datetime.date(2026, 7, 16))
        # Lead site avec utm_content = 'ad-<id>' (convention ADSENG1), sans meta_ad_id.
        self._lead(stage=SIGNED, utm_content='ad-ad_100',
                   canal=Lead.Canal.SITE_WEB)
        res = attribution.variant_attribution(self.company)
        v = res['variants'][0]
        self.assertEqual(v['signed'], 1)
        self.assertEqual(v['cost_per_signature'], '100.00')

    def test_utm_content_name_fuzzy_match(self):
        self._spend(self.ad, '80.00', datetime.date(2026, 7, 16))
        self._lead(stage=SIGNED, utm_content='Reel Casa',
                   canal=Lead.Canal.SITE_WEB)
        res = attribution.variant_attribution(self.company)
        v = res['variants'][0]
        self.assertEqual(v['signed'], 1)

    def test_organic_lead_excluded(self):
        self._spend(self.ad, '100.00', datetime.date(2026, 7, 16))
        # Lead organique : aucun utm, canal non-Meta.
        self._lead(stage=SIGNED, canal=Lead.Canal.TELEPHONE)
        res = attribution.variant_attribution(self.company)
        self.assertEqual(res['organic_excluded_count'], 1)
        self.assertEqual(res['variants'][0]['signed'], 0)
        self.assertEqual(res['unresolved']['leads'], 0)

    def test_meta_channel_no_utm_goes_unresolved(self):
        self._spend(self.ad, '100.00', datetime.date(2026, 7, 16))
        # Lead appel/DM saisi à la main : canal Meta (CTWA) mais aucune clé d'ad.
        self._lead(stage=SIGNED, canal=Lead.Canal.WHATSAPP_CTWA)
        res = attribution.variant_attribution(self.company)
        self.assertEqual(res['unresolved']['leads'], 1)
        self.assertEqual(res['unresolved']['signed'], 1)
        self.assertEqual(res['organic_excluded_count'], 0)
        self.assertEqual(res['variants'][0]['signed'], 0)

    def test_utm_campaign_only_is_unresolved_not_organic(self):
        self._lead(stage=CONTACTED, utm_campaign='Solaire Casa',
                   canal=Lead.Canal.SITE_WEB)
        res = attribution.variant_attribution(self.company)
        self.assertEqual(res['unresolved']['leads'], 1)
        self.assertEqual(res['organic_excluded_count'], 0)

    def test_no_signature_gives_none_cps(self):
        self._spend(self.ad, '50.00', datetime.date(2026, 7, 16))
        self._lead(stage=CONTACTED, meta_ad_id='ad_100')
        res = attribution.variant_attribution(self.company)
        v = res['variants'][0]
        self.assertEqual(v['qualified'], 1)
        self.assertEqual(v['signed'], 0)
        self.assertIsNone(v['cost_per_signature'])
        self.assertEqual(v['cost_per_qualified_lead'], '50.00')

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other', slug='other-attr')
        Lead.objects.create(
            company=other, nom='X', stage=SIGNED, meta_ad_id='ad_100')
        self._spend(self.ad, '100.00', datetime.date(2026, 7, 16))
        self._lead(stage=SIGNED, meta_ad_id='ad_100')
        res = attribution.variant_attribution(self.company)
        # Le lead signé de l'autre société ne compte pas.
        self.assertEqual(res['variants'][0]['signed'], 1)

    def test_new_stage_lead_not_qualified(self):
        self._spend(self.ad, '90.00', datetime.date(2026, 7, 16))
        self._lead(stage=NEW, meta_ad_id='ad_100')
        res = attribution.variant_attribution(self.company)
        v = res['variants'][0]
        self.assertEqual(v['leads'], 1)
        self.assertEqual(v['qualified'], 0)
        self.assertIsNone(v['cost_per_qualified_lead'])

    def test_eng10_campaign_level_unchanged(self):
        # ENG10 (metrics.py) reste fonctionnel et non impacté : il compte par
        # utm_campaign, indépendamment de la jointure par variante d'ADSENG6.
        self._spend(self.ad, '100.00', datetime.date(2026, 7, 16))
        Lead.objects.create(
            company=self.company, nom='Camp Lead', stage=SIGNED,
            utm_campaign='Solaire Casa')
        rows = metrics.cost_per_signature(self.company)
        camp_row = next(r for r in rows if r['campaign_meta_id'] == 'cmp_1')
        self.assertEqual(camp_row['signed_count'], 1)
