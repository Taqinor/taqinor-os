"""PUB35 — Ingestion de l'attribution INCRÉMENTALE native Meta.

Prouve : le probe de disponibilité (ÉTAPE 1) détecte la colonne OU dégrade
proprement, la synchro ad-level ingère l'incrémental SEULEMENT quand le compte
l'expose (sans jamais casser le pull sinon), et le cockpit met résultats
ATTRIBUÉS et INCRÉMENTAUX côte à côte par ad (vide = dégradation propre).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import metrics, tasks
from apps.adsengine.meta_client import (
    INCREMENTAL_ATTRIBUTION_FIELDS, parse_incremental_attribution,
)
from apps.adsengine.models import AdMirror, InsightSnapshot, MetaConnection

DAY = datetime.date(2026, 7, 16)


class FakeIncrementalClient:
    """Client Meta mocké. ``available`` pilote le probe ; ``get_insights`` renvoie
    des rows AVEC ou SANS les colonnes incrémentales selon ``available``."""

    def __init__(self, *, available):
        self.available = available
        self.requested_fields = None

    def incremental_attribution_available(self):
        return self.available

    def get_insights(self, node, *, fields=None, params=None):
        self.requested_fields = fields
        row = {'ad_id': 'ad1', 'date_start': DAY.isoformat(),
               'spend': '10.00', 'impressions': 500, 'results': 4}
        if self.available:
            row['incremental_conversions'] = 3
            row['incremental_conversion_value'] = '1200.5'
        return [row]


class ProbeTests(TestCase):
    def test_parse_extracts_present_incremental_keys(self):
        row = {'incremental_conversions': 3,
               'incremental_conversion_value': [{'value': '10'},
                                                {'value': '5'}]}
        parsed = parse_incremental_attribution(row)
        self.assertEqual(parsed['incremental_conversions'], 3.0)
        self.assertEqual(parsed['incremental_conversion_value'], 15.0)

    def test_parse_empty_when_absent(self):
        self.assertEqual(parse_incremental_attribution({'spend': '10'}), {})

    def test_fields_constant_nonempty(self):
        self.assertTrue(INCREMENTAL_ATTRIBUTION_FIELDS)


class IncrementalSyncTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='IA Co', slug='ia-co')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'x'}, ad_account_id='act_1')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='Ad 1')

    def _snap(self):
        ct = ContentType.objects.get_for_model(AdMirror)
        return InsightSnapshot.objects.get(
            company=self.company, content_type=ct, object_id=self.ad.pk)

    def test_ingests_incremental_when_available(self):
        client = FakeIncrementalClient(available=True)
        tasks._sync_level_insights(
            self.company, self.conn, client, level='ad',
            incremental_available=True)
        snap = self._snap()
        self.assertEqual(snap.incremental_attribution['incremental_conversions'],
                         3.0)
        # Les champs incrémentaux ont bien été DEMANDÉS.
        self.assertIn('incremental_conversions', client.requested_fields)

    def test_degrades_cleanly_when_unavailable(self):
        client = FakeIncrementalClient(available=False)
        tasks._sync_level_insights(
            self.company, self.conn, client, level='ad',
            incremental_available=False)
        snap = self._snap()
        # Rien stocké (dégradation propre) ET les champs n'ont PAS été demandés
        # (un champ inconnu casserait tout le pull).
        self.assertEqual(snap.incremental_attribution, {})
        self.assertNotIn('incremental_conversions', client.requested_fields)


class IncrementalCockpitTests(TestCase):
    def test_attributed_and_incremental_side_by_side(self):
        company = Company.objects.create(nom='CK2 Co', slug='ck2-co')
        ad = AdMirror.objects.create(
            company=company, meta_id='ad1', name='Ad 1')
        ct = ContentType.objects.get_for_model(AdMirror)
        InsightSnapshot.objects.create(
            company=company, content_type=ct, object_id=ad.pk, date=DAY,
            spend='10.00', results=4,
            incremental_attribution={'incremental_conversions': 3.0})
        rows = metrics.ads_cockpit_rows(company, as_of=DAY)
        self.assertEqual(len(rows), 1)
        # Attribué (nb_leads) ET incrémental présents côte à côte.
        self.assertIn('nb_leads', rows[0])
        self.assertEqual(
            rows[0]['attribution_incrementale']['incremental_conversions'], 3.0)

    def test_incremental_empty_when_unavailable(self):
        company = Company.objects.create(nom='CK3 Co', slug='ck3-co')
        ad = AdMirror.objects.create(
            company=company, meta_id='ad1', name='Ad 1')
        ct = ContentType.objects.get_for_model(AdMirror)
        InsightSnapshot.objects.create(
            company=company, content_type=ct, object_id=ad.pk, date=DAY,
            spend='10.00', results=4)
        rows = metrics.ads_cockpit_rows(company, as_of=DAY)
        self.assertEqual(rows[0]['attribution_incrementale'], {})
