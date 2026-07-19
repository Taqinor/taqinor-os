"""PUB78 — Calendrier créatif marocain.

Prouve : seed idempotent ; le backlog est trié par la vraie proximité
calendaire (une saison imminente remonte) ; les fenêtres de recommandation
(J-lead_days) s'ouvrent bien.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import calendar as calendar_mod
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, CreativeCalendarEvent,
)


class SeedCalendarTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cal Co', slug='cal-co')

    def test_seed_is_idempotent(self):
        n1 = calendar_mod.seed_calendar(self.company)
        self.assertEqual(n1, len(calendar_mod.SEED_EVENTS))
        n2 = calendar_mod.seed_calendar(self.company)
        self.assertEqual(n2, 0)  # aucun doublon au deuxième appel
        self.assertEqual(
            CreativeCalendarEvent.objects.filter(company=self.company).count(),
            len(calendar_mod.SEED_EVENTS))

    def test_seeded_tags_present(self):
        calendar_mod.seed_calendar(self.company)
        tags = set(CreativeCalendarEvent.objects
                   .filter(company=self.company)
                   .values_list('tag', flat=True))
        for expected in ('ramadan', 'aid_fitr', 'rentree', 'canicule',
                         'agricole_post_recolte'):
            self.assertIn(expected, tags)


class CalendarWindowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Win Co', slug='win-co')

    def _event(self, tag, debut, fin, lead=30):
        return CreativeCalendarEvent.objects.create(
            company=self.company, tag=tag, label=tag,
            date_debut=debut, date_fin=fin, lead_days=lead)

    def test_recommendation_window_opens_lead_days_before(self):
        ev = self._event(
            'ramadan', datetime.date(2026, 3, 1),
            datetime.date(2026, 3, 30), lead=30)
        # J-40 : pas encore ; J-20 : ouverte ; pendant : ouverte.
        self.assertFalse(ev.is_in_recommendation_window(datetime.date(2026, 1, 20)))
        self.assertTrue(ev.is_in_recommendation_window(datetime.date(2026, 2, 9)))
        self.assertTrue(ev.is_in_recommendation_window(datetime.date(2026, 3, 15)))

    def test_tag_proximity(self):
        self._event('canicule', datetime.date(2026, 7, 1),
                    datetime.date(2026, 8, 31))
        today = datetime.date(2026, 6, 1)
        self.assertEqual(
            calendar_mod.tag_proximity(self.company, 'canicule', today=today),
            30)
        # En pleine saison → proximité 0.
        self.assertEqual(
            calendar_mod.tag_proximity(
                self.company, 'canicule', today=datetime.date(2026, 7, 15)),
            0)
        # Tag inconnu → None.
        self.assertIsNone(
            calendar_mod.tag_proximity(self.company, 'inexistant', today=today))

    def test_upcoming_windows(self):
        self._event('rentree', datetime.date(2026, 9, 1),
                    datetime.date(2026, 9, 15), lead=21)
        rows = calendar_mod.upcoming_windows(
            self.company, today=datetime.date(2026, 8, 20), within_days=45)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tag'], 'rentree')
        self.assertTrue(rows[0]['recommandation_ouverte'])


class BacklogSortTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sort Co', slug='sort-co')
        self.today = datetime.date(2026, 6, 1)
        # Deux saisons : canicule proche (J-30), rentrée lointaine (J-92).
        CreativeCalendarEvent.objects.create(
            company=self.company, tag='canicule', label='Canicule',
            date_debut=datetime.date(2026, 7, 1),
            date_fin=datetime.date(2026, 8, 31), lead_days=45)
        CreativeCalendarEvent.objects.create(
            company=self.company, tag='rentree', label='Rentrée',
            date_debut=datetime.date(2026, 9, 1),
            date_fin=datetime.date(2026, 9, 15), lead_days=21)

    def _item(self, seasonal_tag):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        return CreativeBacklogItem.objects.create(
            company=self.company, asset=asset, seasonal_tag=seasonal_tag)

    def test_backlog_sorted_by_calendar_proximity(self):
        item_far = self._item('rentree')       # J-92
        item_near = self._item('canicule')     # J-30
        item_none = self._item('')             # sans saison → dernier
        ordered = calendar_mod.sort_backlog_items(
            self.company, [item_far, item_none, item_near], today=self.today)
        self.assertEqual(
            [i.id for i in ordered],
            [item_near.id, item_far.id, item_none.id])
