"""ADSDEEP47 — Tests du leaderboard créatif (hook/angle/format, spend-weighted)
+ nuage hook rate × dépense en quadrants FR, barre Motion (benchmark §2).

Prouve : classement group-by sur les tags ADSDEEP46, pondéré par la dépense
(jamais une moyenne simple qui sur-pèserait un petit ad) ; les ads sans tag
sont exclus du classement (comptés à part) ; le nuage classe en 4 quadrants FR
autour de la MÉDIANE (jamais un seuil absolu) et exclut tout ad sans hook rate
calculable ; période sélectionnable ; endpoints gated ``adsengine_view``.
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
from apps.adsengine.models import AdMirror, InsightSnapshot

User = get_user_model()
LEADERBOARD_URL = '/api/django/adsengine/reporting/creatifs/classement/'
SCATTER_URL = '/api/django/adsengine/reporting/creatifs/nuage/'


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


class CreativeLeaderboardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Lead Co', slug='lead-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _ad(self, meta_id, *, hook_tag='', angle_tag='', format_tag=''):
        return AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id,
            hook_tag=hook_tag, angle_tag=angle_tag, format_tag=format_tag)

    def _snap(self, ad, day, *, spend, impressions, results=1,
              video_metrics=None):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=day, spend=spend, impressions=impressions, results=results,
            video_metrics=video_metrics or {})

    def test_groups_by_hook_and_weights_by_spend(self):
        ad1 = self._ad('a1', hook_tag='PAIN')
        ad2 = self._ad('a2', hook_tag='PAIN')
        day = datetime.date(2026, 7, 16)
        # ad1 : petite dépense, hook rate haut. ad2 : grosse dépense, hook rate bas.
        self._snap(ad1, day, spend='100.00', impressions=1000,
                   video_metrics={'s6': 500})  # hook_rate 0.5
        self._snap(ad2, day, spend='900.00', impressions=1000,
                   video_metrics={'s6': 100})  # hook_rate 0.1
        data = reporting.creative_leaderboard(
            self.company, dimension='hook', date_start=day, date_end=day)
        self.assertEqual(len(data['classement']), 1)
        group = data['classement'][0]
        self.assertEqual(group['tag'], 'PAIN')
        self.assertEqual(group['spend'], '1000.00')
        self.assertEqual(group['ad_count'], 2)
        # Pondéré par la dépense : (0.5*100 + 0.1*900) / 1000 = 0.14
        self.assertAlmostEqual(group['hook_rate_weighted'], 0.14, places=4)

    def test_untagged_ads_excluded_and_counted_separately(self):
        ad = self._ad('a1', hook_tag='')
        day = datetime.date(2026, 7, 16)
        self._snap(ad, day, spend='50.00', impressions=1000)
        data = reporting.creative_leaderboard(
            self.company, date_start=day, date_end=day)
        self.assertEqual(data['classement'], [])
        self.assertEqual(data['untagged_count'], 1)

    def test_sorted_by_spend_descending(self):
        ad1 = self._ad('a1', hook_tag='PAIN')
        ad2 = self._ad('a2', hook_tag='ROI')
        day = datetime.date(2026, 7, 16)
        self._snap(ad1, day, spend='50.00', impressions=1000)
        self._snap(ad2, day, spend='500.00', impressions=1000)
        data = reporting.creative_leaderboard(
            self.company, date_start=day, date_end=day)
        self.assertEqual(data['classement'][0]['tag'], 'ROI')
        self.assertEqual(data['classement'][1]['tag'], 'PAIN')

    def test_ad_without_hook_rate_never_dilutes_weighted_average(self):
        ad1 = self._ad('a1', hook_tag='PAIN')
        ad2 = self._ad('a2', hook_tag='PAIN')
        day = datetime.date(2026, 7, 16)
        self._snap(ad1, day, spend='100.00', impressions=1000,
                   video_metrics={'s6': 500})  # hook_rate 0.5
        # ad2 : statique, aucune donnée vidéo → hook_rate None.
        self._snap(ad2, day, spend='900.00', impressions=1000)
        data = reporting.creative_leaderboard(
            self.company, date_start=day, date_end=day)
        group = data['classement'][0]
        # Seul ad1 (hook_rate calculable) participe à la moyenne pondérée.
        self.assertEqual(group['hook_rate_weighted'], 0.5)
        self.assertEqual(group['ad_count'], 2)  # les deux comptent au ranking

    def test_dimension_angle_and_format(self):
        ad = self._ad('a1', hook_tag='PAIN', angle_tag='ROI', format_tag='UGC')
        day = datetime.date(2026, 7, 16)
        self._snap(ad, day, spend='10.00', impressions=100)
        angle_data = reporting.creative_leaderboard(
            self.company, dimension='angle', date_start=day, date_end=day)
        self.assertEqual(angle_data['classement'][0]['tag'], 'ROI')
        format_data = reporting.creative_leaderboard(
            self.company, dimension='format', date_start=day, date_end=day)
        self.assertEqual(format_data['classement'][0]['tag'], 'UGC')

    def test_default_period_is_30_days(self):
        data = reporting.creative_leaderboard(self.company)
        span = (datetime.date.fromisoformat(data['periode']['fin'])
                - datetime.date.fromisoformat(data['periode']['debut']))
        self.assertEqual(span.days, 29)


class CreativeScatterTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Scat Co', slug='scat-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _ad(self, meta_id):
        return AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id)

    def _snap(self, ad, day, *, spend, impressions, video_metrics):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=day, spend=spend, impressions=impressions, results=1,
            video_metrics=video_metrics)

    def test_quadrants_around_median(self):
        day = datetime.date(2026, 7, 16)
        gem = self._ad('gem')       # hook rate haut, dépense basse
        pit = self._ad('pit')       # hook rate bas, dépense haute
        winner = self._ad('winner')  # hook rate haut, dépense haute
        watch = self._ad('watch')   # hook rate bas, dépense basse

        self._snap(gem, day, spend='50.00', impressions=1000,
                   video_metrics={'s6': 500})     # 0.5
        self._snap(pit, day, spend='950.00', impressions=1000,
                   video_metrics={'s6': 50})      # 0.05
        self._snap(winner, day, spend='900.00', impressions=1000,
                   video_metrics={'s6': 600})     # 0.6
        self._snap(watch, day, spend='60.00', impressions=1000,
                   video_metrics={'s6': 60})      # 0.06

        data = reporting.creative_scatter(
            self.company, date_start=day, date_end=day)
        by_ad = {p['ad_meta_id']: p for p in data['points']}
        self.assertEqual(by_ad['gem']['quadrant'],
                         reporting.QUADRANT_HIDDEN_GEM)
        self.assertEqual(by_ad['pit']['quadrant'],
                         reporting.QUADRANT_MONEY_PIT)
        self.assertEqual(by_ad['winner']['quadrant'],
                         reporting.QUADRANT_CONFIRMED_WINNER)
        self.assertEqual(by_ad['watch']['quadrant'],
                         reporting.QUADRANT_WATCH)
        self.assertEqual(by_ad['gem']['quadrant_label_fr'], 'Pépites cachées')
        self.assertEqual(by_ad['pit']['quadrant_label_fr'],
                         'Gouffres à budget')

    def test_ads_without_hook_rate_excluded_from_scatter(self):
        day = datetime.date(2026, 7, 16)
        ad = self._ad('static1')
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=day, spend=Decimal('100.00'), impressions=1000, results=1,
            video_metrics={})
        data = reporting.creative_scatter(
            self.company, date_start=day, date_end=day)
        self.assertEqual(data['points'], [])
        self.assertIsNone(data['median_hook_rate'])

    def test_no_ads_gives_empty_scatter(self):
        data = reporting.creative_scatter(self.company)
        self.assertEqual(data['points'], [])
        self.assertIsNone(data['median_spend'])


class CreativeLeaderboardEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EP2 Co', slug='ep2-co')
        self.viewer = make_user(self.company, 'viewer2', ['adsengine_view'])
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def test_leaderboard_endpoint_returns_data(self):
        ad = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='a1', hook_tag='PAIN')
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=datetime.date(2026, 7, 16), spend=Decimal('10.00'),
            impressions=100, results=1)
        resp = auth(self.viewer).get(LEADERBOARD_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('classement', resp.data)
        self.assertEqual(resp.data['dimension'], 'hook')

    def test_leaderboard_dimension_query_param(self):
        resp = auth(self.viewer).get(LEADERBOARD_URL, {'dimension': 'angle'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['dimension'], 'angle')

    def test_leaderboard_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody2', [])
        self.assertEqual(auth(nobody).get(LEADERBOARD_URL).status_code, 403)

    def test_scatter_endpoint_returns_data(self):
        resp = auth(self.viewer).get(SCATTER_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('points', resp.data)

    def test_scatter_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody3', [])
        self.assertEqual(auth(nobody).get(SCATTER_URL).status_code, 403)

    def test_period_query_params_respected(self):
        resp = auth(self.viewer).get(
            LEADERBOARD_URL, {'debut': '2026-07-01', 'fin': '2026-07-15'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['periode']['debut'], '2026-07-01')
        self.assertEqual(resp.data['periode']['fin'], '2026-07-15')
