"""ADSDEEP7 — Tests du modèle InsightBreakdown : upsert idempotent, unicité par
(company, cible, date, dimension, clé), isolation multi-tenant.
"""
import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import InsightBreakdown


class InsightBreakdownTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BK Co', slug='bk')
        self.camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]
        self.day = datetime.date(2026, 7, 16)

    def test_upsert_idempotent(self):
        InsightBreakdown.upsert(
            self.company, self.camp, date=self.day,
            dimension=InsightBreakdown.Dimension.AGE_GENDER, key='25-34/f',
            spend='10', impressions=100)
        InsightBreakdown.upsert(
            self.company, self.camp, date=self.day,
            dimension=InsightBreakdown.Dimension.AGE_GENDER, key='25-34/f',
            spend='20', impressions=200)
        rows = InsightBreakdown.objects.filter(company=self.company)
        self.assertEqual(rows.count(), 1)  # même clé → 1 ligne mise à jour
        row = rows.get()
        self.assertEqual(float(row.spend), 20.0)
        self.assertEqual(row.impressions, 200)

    def test_different_keys_distinct_rows(self):
        for key in ('25-34/f', '35-44/m'):
            InsightBreakdown.upsert(
                self.company, self.camp, date=self.day,
                dimension=InsightBreakdown.Dimension.AGE_GENDER, key=key,
                spend='5')
        self.assertEqual(
            InsightBreakdown.objects.filter(company=self.company).count(), 2)

    def test_unique_constraint_enforced(self):
        InsightBreakdown.objects.create(
            company=self.company,
            content_type=__import__(
                'django.contrib.contenttypes.models', fromlist=['ContentType']
            ).ContentType.objects.get_for_model(self.camp),
            object_id=self.camp.pk, date=self.day,
            dimension=InsightBreakdown.Dimension.REGION, key='Casablanca',
            spend='3')
        from django.contrib.contenttypes.models import ContentType
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InsightBreakdown.objects.create(
                    company=self.company,
                    content_type=ContentType.objects.get_for_model(self.camp),
                    object_id=self.camp.pk, date=self.day,
                    dimension=InsightBreakdown.Dimension.REGION,
                    key='Casablanca', spend='9')

    def test_tenant_isolation(self):
        other = Company.objects.create(nom='BK B', slug='bkb')
        other_camp = sync.sync_campaigns(other, [{'id': 'c1'}])[0]
        InsightBreakdown.upsert(
            self.company, self.camp, date=self.day,
            dimension=InsightBreakdown.Dimension.HOURLY, key='14', spend='1')
        InsightBreakdown.upsert(
            other, other_camp, date=self.day,
            dimension=InsightBreakdown.Dimension.HOURLY, key='14', spend='2')
        self.assertEqual(
            InsightBreakdown.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            InsightBreakdown.objects.filter(company=other).count(), 1)
