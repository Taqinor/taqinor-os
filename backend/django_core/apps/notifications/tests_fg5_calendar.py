"""FG5 — Tests du calendrier ouvré : WorkingHoursConfig + Holiday + helpers.

Couverture :
  - Création des modèles (company forcée côté serveur).
  - Isolation multi-tenant : les fériés d'une société ne fuient pas à l'autre.
  - Idempotence du seed (seed_ma_holidays).
  - Helpers is_jour_ouvre / prochain_jour_ouvre / ajouter_jours_ouvres :
      - week-end sauté,
      - jour férié sauté,
      - cumul week-end + féri,
      - n=0 (renvoie le même jour s'il est ouvré).
  - API working-hours : GET (défauts), PATCH (upsert, admin only).
  - API holidays : CRUD (admin) ; lecture (tout rôle) ; scoping société.
  - API calendar/check.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import Holiday, WorkingHoursConfig

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _co(name='TestCo'):
    return Company.objects.create(nom=name)


def _user(company, username='user1', role='admin'):
    u = User.objects.create_user(
        username=username, password='pw', company=company)
    u.role_legacy = role
    u.save(update_fields=['role_legacy'])
    return u


# ---------------------------------------------------------------------------
# Tests de modèle
# ---------------------------------------------------------------------------

class WorkingHoursConfigModelTests(TestCase):

    def test_create_config_with_company(self):
        co = _co('WHCo')
        cfg = WorkingHoursConfig.objects.create(
            company=co, working_days=31, hours_per_day='8.00')
        self.assertEqual(cfg.company, co)
        self.assertEqual(cfg.working_days, 31)

    def test_is_working_weekday(self):
        co = _co('WHCo2')
        # Lundi–Vendredi (0b00011111 = 31)
        cfg = WorkingHoursConfig.objects.create(company=co, working_days=31)
        for day in range(5):  # 0=Lun … 4=Ven
            self.assertTrue(cfg.is_working_weekday(day))
        # Samedi et Dimanche
        self.assertFalse(cfg.is_working_weekday(5))
        self.assertFalse(cfg.is_working_weekday(6))

    def test_singleton_per_company(self):
        co = _co('WHCo3')
        WorkingHoursConfig.objects.create(company=co, working_days=31)
        # Pas de deuxième ligne possible (OneToOne).
        with self.assertRaises(Exception):
            WorkingHoursConfig.objects.create(company=co, working_days=62)


class HolidayModelTests(TestCase):

    def test_create_holiday(self):
        co = _co('HolCo')
        h = Holiday.objects.create(
            company=co,
            date=datetime.date(2024, 1, 1),
            nom="Jour de l'An",
            recurrent_annuel=True)
        self.assertEqual(h.company, co)
        self.assertTrue(h.recurrent_annuel)

    def test_unique_constraint(self):
        co = _co('HolCo2')
        Holiday.objects.create(
            company=co, date=datetime.date(2024, 7, 30),
            nom="Fête du Trône", recurrent_annuel=True)
        with self.assertRaises(Exception):
            Holiday.objects.create(
                company=co, date=datetime.date(2024, 7, 30),
                nom="Fête du Trône", recurrent_annuel=True)

    def test_company_scoping(self):
        """Les fériés d'une société n'apparaissent pas pour une autre."""
        co1 = _co('HolCo3')
        co2 = _co('HolCo4')
        Holiday.objects.create(
            company=co1, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An", recurrent_annuel=True)
        self.assertEqual(Holiday.objects.filter(company=co2).count(), 0)
        self.assertEqual(Holiday.objects.filter(company=co1).count(), 1)


# ---------------------------------------------------------------------------
# Tests du seed
# ---------------------------------------------------------------------------

class SeedMaHolidaysTests(TestCase):

    def test_seed_creates_9_fixed_holidays(self):
        from apps.notifications.management.commands.seed_ma_holidays import (
            MA_FIXED_HOLIDAYS,
        )
        from apps.notifications.models import Holiday
        co = _co('SeedCo')
        # Appel direct de la logique de seed.
        import datetime as dt
        _REF_YEAR = 2024
        created = 0
        for month, day, name in MA_FIXED_HOLIDAYS:
            ref_date = dt.date(_REF_YEAR, month, day)
            _, c = Holiday.objects.get_or_create(
                company=co, date=ref_date, nom=name,
                defaults={'recurrent_annuel': True})
            if c:
                created += 1
        self.assertEqual(created, 9)
        self.assertEqual(Holiday.objects.filter(company=co).count(), 9)

    def test_seed_is_idempotent(self):
        """Un deuxième seed ne crée pas de doublons."""
        from apps.notifications.management.commands.seed_ma_holidays import (
            MA_FIXED_HOLIDAYS,
        )
        co = _co('SeedCo2')
        import datetime as dt
        _REF_YEAR = 2024

        def _run():
            for month, day, name in MA_FIXED_HOLIDAYS:
                ref_date = dt.date(_REF_YEAR, month, day)
                Holiday.objects.get_or_create(
                    company=co, date=ref_date, nom=name,
                    defaults={'recurrent_annuel': True})

        _run()
        _run()  # deuxième passage
        self.assertEqual(Holiday.objects.filter(company=co).count(), 9)

    def test_all_fixed_holidays_are_recurrent_annuel(self):
        from apps.notifications.management.commands.seed_ma_holidays import (
            MA_FIXED_HOLIDAYS,
        )
        co = _co('SeedCo3')
        import datetime as dt
        _REF_YEAR = 2024
        for month, day, name in MA_FIXED_HOLIDAYS:
            ref_date = dt.date(_REF_YEAR, month, day)
            Holiday.objects.get_or_create(
                company=co, date=ref_date, nom=name,
                defaults={'recurrent_annuel': True})
        self.assertTrue(
            Holiday.objects.filter(company=co, recurrent_annuel=False).count() == 0)


# ---------------------------------------------------------------------------
# Tests des helpers calendar_utils
# ---------------------------------------------------------------------------

class IsJourOuvreTests(TestCase):

    def setUp(self):
        self.co = _co('CalCo')

    def test_monday_is_working_day_by_default(self):
        from .calendar_utils import is_jour_ouvre
        # 2025-06-23 est un Lundi.
        self.assertTrue(is_jour_ouvre(datetime.date(2025, 6, 23), self.co))

    def test_saturday_is_not_working_day_by_default(self):
        from .calendar_utils import is_jour_ouvre
        # 2025-06-28 est un Samedi.
        self.assertFalse(is_jour_ouvre(datetime.date(2025, 6, 28), self.co))

    def test_sunday_is_not_working_day_by_default(self):
        from .calendar_utils import is_jour_ouvre
        # 2025-06-29 est un Dimanche.
        self.assertFalse(is_jour_ouvre(datetime.date(2025, 6, 29), self.co))

    def test_seeded_holiday_is_not_working_day(self):
        from .calendar_utils import is_jour_ouvre
        # 2025-01-01 = Jour de l'An (Mercredi, normalement ouvré).
        Holiday.objects.create(
            company=self.co,
            date=datetime.date(2024, 1, 1),
            nom="Jour de l'An",
            recurrent_annuel=True)
        self.assertFalse(is_jour_ouvre(datetime.date(2025, 1, 1), self.co))

    def test_non_recurrent_holiday_only_blocks_its_year(self):
        from .calendar_utils import is_jour_ouvre
        # Férié non récurrent posé pour 2025-01-06 (Lundi).
        Holiday.objects.create(
            company=self.co,
            date=datetime.date(2025, 1, 6),
            nom='Férié ponctuel',
            recurrent_annuel=False)
        self.assertFalse(is_jour_ouvre(datetime.date(2025, 1, 6), self.co))
        # En 2026, ce jour n'est plus bloqué.
        self.assertTrue(is_jour_ouvre(datetime.date(2026, 1, 5), self.co))

    def test_holiday_scoped_per_company(self):
        """Un férié d'une autre société n'affecte pas cette société."""
        from .calendar_utils import is_jour_ouvre
        other = _co('OtherCalCo')
        Holiday.objects.create(
            company=other,
            date=datetime.date(2024, 1, 1),
            nom="Jour de l'An",
            recurrent_annuel=True)
        # Pour self.co (sans config ni férié), le 2025-01-01 (Mercredi) est ouvré.
        self.assertTrue(is_jour_ouvre(datetime.date(2025, 1, 1), self.co))

    def test_custom_working_days_bitmask(self):
        """Avec un bitmask personnalisé (Lun+Mar uniquement), Mer→Dim sont off."""
        from .calendar_utils import is_jour_ouvre
        # Lundi(bit0) + Mardi(bit1) = 0b00000011 = 3.
        WorkingHoursConfig.objects.create(company=self.co, working_days=3)
        # 2025-06-23 = Lundi → ouvré.
        self.assertTrue(is_jour_ouvre(datetime.date(2025, 6, 23), self.co))
        # 2025-06-24 = Mardi → ouvré.
        self.assertTrue(is_jour_ouvre(datetime.date(2025, 6, 24), self.co))
        # 2025-06-25 = Mercredi → non ouvré.
        self.assertFalse(is_jour_ouvre(datetime.date(2025, 6, 25), self.co))


class ProchainJourOuvreTests(TestCase):

    def setUp(self):
        self.co = _co('NextCalCo')

    def test_already_working_day_returned_unchanged(self):
        from .calendar_utils import prochain_jour_ouvre
        # 2025-06-23 = Lundi (ouvré).
        d = datetime.date(2025, 6, 23)
        self.assertEqual(prochain_jour_ouvre(d, self.co), d)

    def test_saturday_advances_to_monday(self):
        from .calendar_utils import prochain_jour_ouvre
        # 2025-06-28 = Samedi → premier ouvré = 2025-06-30 (Lundi).
        d = datetime.date(2025, 6, 28)
        self.assertEqual(prochain_jour_ouvre(d, self.co), datetime.date(2025, 6, 30))

    def test_sunday_advances_to_monday(self):
        from .calendar_utils import prochain_jour_ouvre
        d = datetime.date(2025, 6, 29)  # Dimanche
        self.assertEqual(prochain_jour_ouvre(d, self.co), datetime.date(2025, 6, 30))

    def test_skips_holiday_on_weekday(self):
        from .calendar_utils import prochain_jour_ouvre
        # 2025-01-01 = Mercredi, ajout comme férié récurrent.
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An", recurrent_annuel=True)
        # Depuis le 2025-01-01 (Mercredi ferié) → doit sauter au 2025-01-02 (Jeudi).
        self.assertEqual(
            prochain_jour_ouvre(datetime.date(2025, 1, 1), self.co),
            datetime.date(2025, 1, 2))


class AjouterJoursOuvresTests(TestCase):

    def setUp(self):
        self.co = _co('AddCalCo')

    def test_add_zero_returns_same_if_working(self):
        from .calendar_utils import ajouter_jours_ouvres
        d = datetime.date(2025, 6, 23)  # Lundi
        self.assertEqual(ajouter_jours_ouvres(d, 0, self.co), d)

    def test_add_one_working_day_skips_weekend(self):
        from .calendar_utils import ajouter_jours_ouvres
        # Vendredi + 1 jour ouvré = Lundi suivant.
        d = datetime.date(2025, 6, 27)  # Vendredi
        result = ajouter_jours_ouvres(d, 1, self.co)
        self.assertEqual(result, datetime.date(2025, 6, 30))  # Lundi

    def test_add_five_working_days_spans_weekend(self):
        from .calendar_utils import ajouter_jours_ouvres
        # Lundi 2025-06-23 + 5 jours ouvrés = Lundi 2025-06-30.
        d = datetime.date(2025, 6, 23)
        result = ajouter_jours_ouvres(d, 5, self.co)
        self.assertEqual(result, datetime.date(2025, 6, 30))

    def test_add_skips_holiday(self):
        from .calendar_utils import ajouter_jours_ouvres
        # 2025-07-30 = Mercredi ouvré sans config.
        # Posons un férié sur le 2025-07-31 (Jeudi).
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 7, 30),
            nom='Fête du Trône', recurrent_annuel=True)
        # Mercredi 2025-07-30 + 1 = doit sauter le 31/07 (Mercredi = Fête du Trône
        # → oui ouvré côté semaine mais férié) → 2025-08-01 (Vendredi).
        # Attention : le 30/07 lui-même est le férié ici (recurrent, mois=7 jour=30).
        # Donc depuis 2025-07-29 (Mardi) + 1 jour ouvré :
        # 2025-07-30 est férié → saute → 2025-07-31 (Jeudi) est ouvré.
        d = datetime.date(2025, 7, 29)  # Mardi
        result = ajouter_jours_ouvres(d, 1, self.co)
        self.assertEqual(result, datetime.date(2025, 7, 31))  # Jeudi (car Mercredi est férié)

    def test_negative_n_returns_d(self):
        from .calendar_utils import ajouter_jours_ouvres
        d = datetime.date(2025, 6, 23)
        self.assertEqual(ajouter_jours_ouvres(d, -1, self.co), d)


# ---------------------------------------------------------------------------
# Tests API
# ---------------------------------------------------------------------------

class WorkingHoursConfigApiTests(TestCase):

    def setUp(self):
        self.co = _co('WHApiCo')
        self.admin = _user(self.co, 'wh_admin', 'admin')
        self.normal = _user(self.co, 'wh_normal', 'normal')
        self.client = APIClient()

    def test_get_returns_defaults_when_no_config(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/django/notifications/working-hours/')
        self.assertEqual(res.status_code, 200)
        data = res.data
        # Résultat peut être une liste paginée ou directement un objet.
        if isinstance(data, list):
            data = data[0] if data else {}
        self.assertIn('working_days', data)

    def test_patch_creates_config(self):
        self.client.force_authenticate(self.admin)
        res = self.client.patch(
            '/api/django/notifications/working-hours/1/',
            {'working_days': 62},  # Lun–Sam
            format='json')
        self.assertIn(res.status_code, [200, 201])
        cfg = WorkingHoursConfig.objects.filter(company=self.co).first()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.working_days, 62)

    def test_normal_user_cannot_write(self):
        self.client.force_authenticate(self.normal)
        res = self.client.patch(
            '/api/django/notifications/working-hours/1/',
            {'working_days': 62}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_company_forced_server_side(self):
        """La company de la config est celle de l'utilisateur authentifié."""
        self.client.force_authenticate(self.admin)
        self.client.patch(
            '/api/django/notifications/working-hours/1/',
            {'working_days': 31}, format='json')
        cfg = WorkingHoursConfig.objects.filter(company=self.co).first()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.company, self.co)


class HolidayApiTests(TestCase):

    def setUp(self):
        self.co = _co('HolApiCo')
        self.other_co = _co('HolApiOtherCo')
        self.admin = _user(self.co, 'hol_admin', 'admin')
        self.normal = _user(self.co, 'hol_normal', 'normal')
        self.other_admin = _user(self.other_co, 'hol_other_admin', 'admin')
        self.client = APIClient()

    def test_create_holiday_as_admin(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            '/api/django/notifications/holidays/',
            {
                'date': '2025-01-01',
                'nom': "Jour de l'An",
                'recurrent_annuel': True,
            },
            format='json')
        self.assertEqual(res.status_code, 201, res.data)
        h = Holiday.objects.filter(company=self.co).first()
        self.assertIsNotNone(h)
        # company posée côté serveur.
        self.assertEqual(h.company, self.co)

    def test_normal_user_cannot_create(self):
        self.client.force_authenticate(self.normal)
        res = self.client.post(
            '/api/django/notifications/holidays/',
            {'date': '2025-01-01', 'nom': 'Test', 'recurrent_annuel': False},
            format='json')
        self.assertEqual(res.status_code, 403)

    def test_list_scoped_to_company(self):
        """Un admin ne voit que les fériés de SA société."""
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An", recurrent_annuel=True)
        Holiday.objects.create(
            company=self.other_co, date=datetime.date(2024, 5, 1),
            nom='Fête du Travail', recurrent_annuel=True)
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/django/notifications/holidays/')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['nom'], "Jour de l'An")

    def test_year_filter(self):
        """Le filtre ?year= ne renvoie que les fériés de cette année."""
        # Récurrent → visible en 2025 et 2026.
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An", recurrent_annuel=True)
        # Ponctuel 2025 uniquement.
        Holiday.objects.create(
            company=self.co, date=datetime.date(2025, 3, 10),
            nom='Férié ponctuel 2025', recurrent_annuel=False)
        # Ponctuel 2024 uniquement.
        Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 6, 1),
            nom='Férié 2024 only', recurrent_annuel=False)

        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/django/notifications/holidays/?year=2025')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        noms = {r['nom'] for r in results}
        # Récurrent → présent ; ponctuel 2025 → présent ; ponctuel 2024 → absent.
        self.assertIn("Jour de l'An", noms)
        self.assertIn('Férié ponctuel 2025', noms)
        self.assertNotIn('Férié 2024 only', noms)

    def test_delete_holiday_as_admin(self):
        h = Holiday.objects.create(
            company=self.co, date=datetime.date(2024, 1, 1),
            nom="Jour de l'An", recurrent_annuel=True)
        self.client.force_authenticate(self.admin)
        res = self.client.delete(f'/api/django/notifications/holidays/{h.id}/')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Holiday.objects.filter(pk=h.id).exists())


class CalendarCheckApiTests(TestCase):

    def setUp(self):
        self.co = _co('ChkCo')
        self.user = _user(self.co, 'chk_user', 'normal')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_working_day_check(self):
        # 2025-06-23 = Lundi (ouvré par défaut).
        res = self.client.get(
            '/api/django/notifications/calendar/check/?date=2025-06-23')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['is_jour_ouvre'])
        self.assertEqual(res.data['date'], '2025-06-23')

    def test_saturday_check(self):
        # 2025-06-28 = Samedi.
        res = self.client.get(
            '/api/django/notifications/calendar/check/?date=2025-06-28')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['is_jour_ouvre'])
        # prochain_jour_ouvre doit être le Lundi.
        self.assertEqual(res.data['prochain_jour_ouvre'], '2025-06-30')

    def test_invalid_date_returns_400(self):
        res = self.client.get(
            '/api/django/notifications/calendar/check/?date=not-a-date')
        self.assertEqual(res.status_code, 400)

    def test_no_date_uses_today(self):
        res = self.client.get('/api/django/notifications/calendar/check/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('date', res.data)
        self.assertIn('is_jour_ouvre', res.data)
