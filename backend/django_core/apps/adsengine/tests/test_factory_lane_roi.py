"""PUB81 — Tests du ROI par LANE de fabrique créative.

``CreativeAsset.cost_cents`` est peuplé par chaque adaptateur (zapcap/fal/
templated/…) et n'était lu NULLE PART. Prouve :

  * le coût-par-résultat est calculé PAR LANE (``source_lane``, ``'manuel'``
    en repli pour un asset sans lane) ;
  * le coût d'un asset RÉUTILISÉ sur plusieurs ads (recombinaison) n'est
    compté QU'UNE FOIS (sunk cost), pas dupliqué par ad ;
  * une lane sans résultat mesurable renvoie ``None`` (jamais un coût-par-
    résultat fabriqué) et finit en bas du classement ;
  * l'endpoint est gaté ``adsengine_view``.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import reporting
from apps.adsengine.models import (
    AdMirror, CreativeAsset, Experiment, ExperimentArm, InsightSnapshot,
)

User = get_user_model()
ROI_URL = '/api/django/adsengine/reporting/creatifs/roi-lane/'


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


class FactoryLaneRoiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Roi Co', slug='roi-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)
        self.exp = Experiment.objects.create(company=self.company, name='E')
        self.day = datetime.date(2026, 7, 16)

    def _asset(self, lane, cost_cents):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL,
            source_lane=lane, cost_cents=cost_cents)

    def _wire_ad(self, meta_id, asset, *, results=None, spend=None):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id)
        ExperimentArm.objects.create(
            company=self.company, experiment=self.exp, creative_asset=asset,
            label=meta_id, ad_id=meta_id)
        if results is not None:
            InsightSnapshot.objects.create(
                company=self.company, content_type=self.ct, object_id=ad.pk,
                date=self.day, spend=Decimal(spend), results=results)
        return ad

    def test_cost_per_result_by_lane(self):
        asset_zapcap = self._asset('zapcap', 2000)
        self._wire_ad('ad_z', asset_zapcap, results=10, spend='100.00')
        asset_manual = self._asset('', 500)
        self._wire_ad('ad_m', asset_manual, results=5, spend='50.00')

        data = reporting.factory_lane_roi(
            self.company, date_start=self.day, date_end=self.day)
        lanes = {row['lane']: row for row in data['lanes']}
        self.assertEqual(lanes['zapcap']['cost_cents_total'], 2000)
        self.assertEqual(lanes['zapcap']['results'], 10)
        self.assertEqual(lanes['zapcap']['cost_per_result_centimes'], 200.0)
        # Asset sans lane → groupé sous 'manuel'.
        self.assertEqual(lanes['manuel']['cost_per_result_centimes'], 100.0)
        # Meilleur ROI (coût-par-résultat le plus BAS) d'abord.
        self.assertEqual(data['lanes'][0]['lane'], 'manuel')

    def test_no_results_gives_none_cost(self):
        asset = self._asset('fal', 1000)
        self._wire_ad('ad_x', asset)  # aucun InsightSnapshot → 0 résultat.
        data = reporting.factory_lane_roi(
            self.company, date_start=self.day, date_end=self.day)
        self.assertEqual(len(data['lanes']), 1)
        self.assertIsNone(data['lanes'][0]['cost_per_result_centimes'])
        self.assertEqual(data['lanes'][0]['results'], 0)

    def test_reused_asset_cost_counted_once(self):
        asset = self._asset('templated', 900)
        self._wire_ad('ad_1', asset, results=3, spend='30.00')
        # Le MÊME asset réutilisé sur une 2e ad (recombinaison ADSENG18).
        self._wire_ad('ad_2', asset, results=3, spend='30.00')

        data = reporting.factory_lane_roi(
            self.company, date_start=self.day, date_end=self.day)
        lane = data['lanes'][0]
        self.assertEqual(lane['assets_count'], 1)
        self.assertEqual(lane['cost_cents_total'], 900)  # jamais 1800.
        self.assertEqual(lane['results'], 6)

    def test_no_assets_gives_empty(self):
        data = reporting.factory_lane_roi(self.company)
        self.assertEqual(data['lanes'], [])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Roi', slug='other-roi')
        CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.REEL,
            source_lane='fal', cost_cents=100)
        data = reporting.factory_lane_roi(self.company)
        self.assertEqual(data['lanes'], [])


class FactoryLaneRoiEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RoiEp Co', slug='roiep-co')
        self.viewer = make_user(self.company, 'roi-viewer', ['adsengine_view'])

    def test_endpoint_returns_shape(self):
        resp = auth(self.viewer).get(ROI_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('lanes', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'roi-nobody', [])
        self.assertEqual(auth(nobody).get(ROI_URL).status_code, 403)
