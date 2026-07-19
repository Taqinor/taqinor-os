"""PUB80 — Tests du rapport « trous de couverture » (formats + segments).

Prouve :
  * ``format_coverage`` — carrousel/collection sont structurellement JAMAIS
    modélisés (``AssetType`` ne les couvre pas) ; un type modélisé mais jamais
    utilisé par la société ressort séparément ; les types réellement utilisés
    sont comptés ;
  * ``segment_coverage`` — un segment (âge×genre/région) à forte dépense
    RELATIVE (>= médiane du lot, jamais un seuil absolu) dont AUCUNE ad
    tagguée (hook/angle) ne l'a atteint est signalé ; un segment couvert par
    au moins une ad taguée ou sous la médiane est exclu ;
  * l'endpoint combiné est gaté ``adsengine_view``.
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

from apps.adsengine import coverage
from apps.adsengine.models import AdMirror, CreativeAsset, InsightBreakdown

User = get_user_model()
COVERAGE_URL = '/api/django/adsengine/reporting/couverture/'


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


class FormatCoverageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fmt Co', slug='fmt-co')

    def test_carousel_and_collection_always_never_modeled(self):
        data = coverage.format_coverage(self.company)
        formats = {f['format'] for f in data['jamais_modelises']}
        self.assertEqual(formats, {'carousel', 'collection'})

    def test_no_assets_all_modeled_types_never_used(self):
        data = coverage.format_coverage(self.company)
        formats = {f['format'] for f in data['modelises_jamais_utilises']}
        self.assertEqual(formats, {'reel', 'static', 'explainer'})
        self.assertEqual(data['formats_utilises'], [])

    def test_used_type_excluded_from_never_used_and_counted(self):
        CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        data = coverage.format_coverage(self.company)
        never_used = {f['format'] for f in data['modelises_jamais_utilises']}
        self.assertNotIn('static', never_used)
        used = {f['format']: f['count'] for f in data['formats_utilises']}
        self.assertEqual(used['static'], 2)

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Fmt', slug='other-fmt')
        CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC)
        data = coverage.format_coverage(self.company)
        self.assertEqual(data['formats_utilises'], [])


class SegmentCoverageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Seg Co', slug='seg-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _ad(self, meta_id, *, hook_tag=''):
        return AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id,
            hook_tag=hook_tag)

    def test_high_spend_untagged_segment_flagged(self):
        untagged = self._ad('a1')
        tagged = self._ad('a2', hook_tag='PAIN')
        day = datetime.date(2026, 7, 16)
        InsightBreakdown.upsert(
            self.company, untagged, date=day, dimension='age_gender',
            key='25-34/f', spend=Decimal('500.00'))
        InsightBreakdown.upsert(
            self.company, tagged, date=day, dimension='age_gender',
            key='35-44/f', spend=Decimal('500.00'))
        InsightBreakdown.upsert(
            self.company, untagged, date=day, dimension='age_gender',
            key='18-24/m', spend=Decimal('50.00'))

        data = coverage.segment_coverage(
            self.company, date_start=day, date_end=day)
        gaps = data['segments_non_couverts']
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]['dimension'], 'age_gender')
        self.assertEqual(gaps[0]['segment'], '25-34/f')
        self.assertEqual(gaps[0]['spend'], '500.00')

    def test_tagged_ad_covering_segment_excludes_it(self):
        tagged = self._ad('a3', hook_tag='ROI')
        day = datetime.date(2026, 7, 16)
        InsightBreakdown.upsert(
            self.company, tagged, date=day, dimension='region',
            key='Casablanca', spend=Decimal('1000.00'))
        data = coverage.segment_coverage(
            self.company, date_start=day, date_end=day)
        self.assertEqual(data['segments_non_couverts'], [])

    def test_no_breakdown_data_gives_empty_report(self):
        self._ad('a4')
        data = coverage.segment_coverage(self.company)
        self.assertEqual(data['segments_non_couverts'], [])
        self.assertIsNone(data['median_spend'])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Seg', slug='other-seg')
        other_ad = AdMirror.objects.create(
            company=other, meta_id='oa1', name='oa1')
        day = datetime.date(2026, 7, 16)
        InsightBreakdown.upsert(
            other, other_ad, date=day, dimension='age_gender', key='25-34/f',
            spend=Decimal('900.00'))
        data = coverage.segment_coverage(
            self.company, date_start=day, date_end=day)
        self.assertEqual(data['segments_non_couverts'], [])


class CoverageReportEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CovEp Co', slug='covep-co')
        self.viewer = make_user(self.company, 'cov-viewer', ['adsengine_view'])

    def test_endpoint_returns_combined_shape(self):
        resp = auth(self.viewer).get(COVERAGE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('formats', resp.data)
        self.assertIn('segments', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'cov-nobody', [])
        self.assertEqual(auth(nobody).get(COVERAGE_URL).status_code, 403)
