"""PUB24 — None-protection des 4 champs CŒUR d'``upsert_insight``.

Avant : ``spend``/``results``/``frequency``/``cpl`` s'écrivaient inconditionnellement
— un re-sync PARTIEL (Meta ne renvoie pas un champ un jour donné) les écrasait en
NULL. Après : mêmes règles que les colonnes ADSDEEP1 — None n'est jamais écrit,
mais 0 explicite l'est.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot

DAY = datetime.date(2026, 7, 16)


class CoreNoneProtectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NP Co', slug='np-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')

    def _snap(self):
        return InsightSnapshot.objects.get(
            company=self.company, object_id=self.camp.pk, date=DAY)

    def test_partial_resync_does_not_null_core_metrics(self):
        # 1) synchro complète.
        sync.upsert_insight(
            self.company, self.camp, date=DAY, spend='100.00', results=5,
            frequency='1.50', cpl='20.00')
        # 2) re-sync PARTIEL : seul spend fourni, le reste None.
        sync.upsert_insight(
            self.company, self.camp, date=DAY, spend='120.00')
        snap = self._snap()
        self.assertEqual(snap.spend, Decimal('120.00'))  # mis à jour
        self.assertEqual(snap.results, 5)                # préservé
        self.assertEqual(snap.frequency, Decimal('1.50'))  # préservé
        self.assertEqual(snap.cpl, Decimal('20.00'))     # préservé

    def test_all_none_resync_preserves_everything(self):
        sync.upsert_insight(
            self.company, self.camp, date=DAY, spend='100.00', results=5,
            frequency='1.50', cpl='20.00')
        # Re-sync sans AUCUN champ cœur → rien n'est écrasé.
        sync.upsert_insight(self.company, self.camp, date=DAY)
        snap = self._snap()
        self.assertEqual(snap.spend, Decimal('100.00'))
        self.assertEqual(snap.results, 5)

    def test_explicit_zero_is_written(self):
        sync.upsert_insight(
            self.company, self.camp, date=DAY, spend='100.00', results=5)
        # 0 explicite (jour à dépense nulle réelle) N'EST PAS None → écrit.
        sync.upsert_insight(
            self.company, self.camp, date=DAY, spend='0', results=0)
        snap = self._snap()
        self.assertEqual(snap.spend, Decimal('0'))
        self.assertEqual(snap.results, 0)

    def test_first_partial_insert_creates_row(self):
        # Un premier upsert partiel crée bien la ligne (champs absents = NULL).
        sync.upsert_insight(self.company, self.camp, date=DAY, spend='50.00')
        snap = self._snap()
        self.assertEqual(snap.spend, Decimal('50.00'))
        self.assertIsNone(snap.results)
