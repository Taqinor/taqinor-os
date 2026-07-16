"""ENGFIX4 — Le total signatures compte les leads DISTINCTS, jamais la somme.

Deux miroirs de campagne de MÊME nom partagent la même clé d'attribution
(``utm_campaign`` = ``name``) → le même bucket de leads signés. L'ancien agrégat
sommait ``signed_count`` par ligne : chaque lead comptait deux fois, gonflant le
total et écrasant le coût-par-signature héros. On prouve ici que le total est
désormais le nombre de leads DISTINCTS (union des ids), la dépense restant
sommée par miroir.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.stages import SIGNED

from apps.adsengine import metrics
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot


class DistinctSignatureCountTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Dedup Co', slug='dedup-co')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)
        # Deux miroirs de MÊME nom (mirroirs jumeaux) mais meta_id distincts.
        self.camp1 = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Solaire Casa',
            status='PAUSED')
        self.camp2 = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c2', name='Solaire Casa',
            status='PAUSED')

    def _spend(self, camp, amount):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=camp.pk,
            date=datetime.date(2026, 7, 16), spend=amount, results=1)

    def test_summary_counts_each_lead_once(self):
        self._spend(self.camp1, '300.00')
        self._spend(self.camp2, '150.00')
        # 3 leads signés attribués à « Solaire Casa » (bucket partagé par les 2).
        for _ in range(3):
            Lead.objects.create(
                company=self.company, nom='Prospect',
                utm_campaign='Solaire Casa', stage=SIGNED)

        per_campaign = metrics.cost_per_signature(self.company)
        # Les deux lignes portent le MÊME bucket signé (3 chacune) — la somme
        # naïve donnerait 6.
        self.assertEqual(len(per_campaign), 2)
        self.assertEqual(
            sum(row['signed_count'] for row in per_campaign), 6)

        summary = metrics.cost_per_signature_summary(self.company)
        # Total DISTINCT = 3 (pas 6) ; dépense = somme des miroirs = 450.
        self.assertEqual(summary['total_signed'], 3)
        self.assertEqual(Decimal(summary['total_spend']), Decimal('450.00'))
        # Héros coût-par-signature calculé sur le compte distinct : 450/3 = 150
        # (et NON 450/6 = 75, la valeur gonflée du double-comptage).
        self.assertEqual(
            Decimal(summary['cost_per_signature']), Decimal('150'))
