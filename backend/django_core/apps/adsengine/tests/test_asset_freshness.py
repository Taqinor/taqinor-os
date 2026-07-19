"""PUB76 — Expiration / rafraîchissement des assets.

Prouve : le job hebdo marque « à revoir » (jamais un retrait auto) un asset qui
cite une version de FactTable RÉVISÉE depuis (chiffre périmé), un asset expiré,
et une créa saisonnière hors fenêtre — par ordre de priorité, idempotent.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import tasks
from apps.adsengine.models import CreativeAsset, FactTable

TODAY = datetime.date(2026, 7, 19)
PAST = datetime.date(2026, 6, 1)
FUTURE = datetime.date(2026, 12, 1)


def make_asset(company, **kw):
    defaults = dict(
        company=company, asset_type=CreativeAsset.AssetType.STATIC)
    defaults.update(kw)
    return CreativeAsset.objects.create(**defaults)


class AssetFreshnessTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fresh Co', slug='fresh-co')

    def _publish_version(self):
        table = FactTable.create_draft(self.company)
        table.publish()
        return table

    def test_revised_facts_flag_older_assets(self):
        v1 = self._publish_version()  # version 1 publiée
        asset = make_asset(self.company, facts_version=v1.version)
        # Une nouvelle version est publiée : l'asset cite désormais l'ancienne.
        self._publish_version()  # version 2 publiée (dépublie v1)
        counts = tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        self.assertEqual(counts['fait_revise'], 1)
        asset.refresh_from_db()
        self.assertTrue(asset.needs_review)
        self.assertEqual(asset.review_reason, 'fait_revise')

    def test_current_version_asset_not_flagged(self):
        v1 = self._publish_version()
        asset = make_asset(self.company, facts_version=v1.version)
        counts = tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        self.assertEqual(counts['fait_revise'], 0)
        asset.refresh_from_db()
        self.assertFalse(asset.needs_review)

    def test_expired_asset_flagged(self):
        asset = make_asset(self.company, expires_at=PAST)
        counts = tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        self.assertEqual(counts['expire'], 1)
        asset.refresh_from_db()
        self.assertEqual(asset.review_reason, 'expire')

    def test_future_expiry_not_flagged(self):
        asset = make_asset(self.company, expires_at=FUTURE)
        counts = tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        self.assertEqual(counts['expire'], 0)
        asset.refresh_from_db()
        self.assertFalse(asset.needs_review)

    def test_seasonal_review_due_flagged(self):
        asset = make_asset(self.company, review_after=PAST)
        counts = tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        self.assertEqual(counts['a_revoir'], 1)
        asset.refresh_from_db()
        self.assertEqual(asset.review_reason, 'a_revoir')

    def test_idempotent(self):
        make_asset(self.company, expires_at=PAST)
        tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        counts2 = tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        self.assertEqual(counts2['expire'], 0)  # déjà marqué

    def test_facts_revised_takes_priority_over_expiry(self):
        v1 = self._publish_version()
        asset = make_asset(
            self.company, facts_version=v1.version, expires_at=PAST)
        self._publish_version()  # v2 → v1 révisée
        tasks.flag_stale_assets_for_company(self.company, today=TODAY)
        asset.refresh_from_db()
        self.assertEqual(asset.review_reason, 'fait_revise')

    def test_shared_task_runs_across_companies(self):
        make_asset(self.company, expires_at=PAST)
        totals = tasks.flag_stale_assets()
        self.assertGreaterEqual(totals['expire'], 1)
