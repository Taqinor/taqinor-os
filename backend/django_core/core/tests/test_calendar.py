"""Tests DC26 — référentiel calendrier marocain (jours ouvrés + fériés).

Couvre :
  * week-end (samedi/dimanche) + fériés fixes/mobiles ;
  * next_working_day saute week-ends et fériés ;
  * add_working_days (avant/après, n=0) ;
  * count_working_days inclusif + intervalle inversé ;
  * extra_holidays personnalisés.
"""
import datetime

from django.test import SimpleTestCase

from core import calendar as cal


class CalendarTests(SimpleTestCase):
    def test_weekend_detection(self):
        # 2026-06-27 = samedi, 2026-06-28 = dimanche, 2026-06-29 = lundi.
        self.assertTrue(cal.is_weekend(datetime.date(2026, 6, 27)))
        self.assertTrue(cal.is_weekend(datetime.date(2026, 6, 28)))
        self.assertFalse(cal.is_weekend(datetime.date(2026, 6, 29)))

    def test_fixed_holiday(self):
        # Fête du Travail (1er mai) — férié fixe.
        self.assertTrue(cal.is_holiday(datetime.date(2026, 5, 1)))
        self.assertFalse(cal.is_working_day(datetime.date(2026, 5, 1)))

    def test_movable_holiday_known_year(self):
        # Aïd al-Fitr 2026 (jeu de départ).
        self.assertTrue(cal.is_holiday(datetime.date(2026, 3, 20)))

    def test_next_working_day_skips_weekend(self):
        # Vendredi 2026-06-26 → lundi 2026-06-29 (saute le week-end).
        nxt = cal.next_working_day(datetime.date(2026, 6, 26))
        self.assertEqual(nxt, datetime.date(2026, 6, 29))

    def test_next_working_day_skips_holiday(self):
        # 2026-04-30 (jeudi) → saute le 1er mai (férié) ET le week-end → 2026-05-04.
        nxt = cal.next_working_day(datetime.date(2026, 4, 30))
        self.assertEqual(nxt, datetime.date(2026, 5, 4))

    def test_add_working_days(self):
        start = datetime.date(2026, 6, 29)  # lundi
        # +4 jours ouvrés → vendredi 2026-07-03.
        self.assertEqual(cal.add_working_days(start, 4),
                         datetime.date(2026, 7, 3))
        # n=0 renvoie tel quel.
        self.assertEqual(cal.add_working_days(start, 0), start)
        # négatif = vers le passé (lundi -1 ouvré → vendredi précédent).
        self.assertEqual(cal.add_working_days(start, -1),
                         datetime.date(2026, 6, 26))

    def test_count_working_days_inclusive(self):
        # Lundi 2026-06-29 → dimanche 2026-07-05 : lun-ven = 5 jours ouvrés.
        n = cal.count_working_days(datetime.date(2026, 6, 29),
                                   datetime.date(2026, 7, 5))
        self.assertEqual(n, 5)

    def test_count_working_days_reversed_is_zero(self):
        n = cal.count_working_days(datetime.date(2026, 7, 5),
                                   datetime.date(2026, 6, 29))
        self.assertEqual(n, 0)

    def test_extra_holiday_param(self):
        d = datetime.date(2026, 6, 30)  # mardi ouvré
        self.assertTrue(cal.is_working_day(d))
        # Marqué férié local via extra_holidays.
        self.assertFalse(cal.is_working_day(d, extra_holidays=[d]))

    def test_datetime_accepted(self):
        dt = datetime.datetime(2026, 5, 1, 9, 30)
        self.assertTrue(cal.is_holiday(dt))
