"""NTHOT11 — Tableau de bord RevPAR/ADR/TO.

Done = les 4 KPI se calculent juste sur un jeu de données multi-chambres avec
annulations/no-show exclus du dénominateur revenus, tests.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.hospitality import selectors
from apps.hospitality.models import Chambre, Reservation, TypeChambre

from .helpers import auth, make_company, make_user


class DashboardHotellerieTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-dash', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        # 2 chambres, fenêtre de 10 jours → 20 nuits disponibles.
        self.chambre1 = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1201')
        self.chambre2 = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1202')
        self.debut = datetime.date(2026, 8, 1)
        self.fin = datetime.date(2026, 8, 11)  # exclusive → 10 jours

    def test_kpis_avec_annulation_et_no_show_exclus(self):
        # Réservation vendue : 4 nuits à 500 = 2000 revenus.
        Reservation.objects.create(
            company=self.co, chambre=self.chambre1,
            date_arrivee=datetime.date(2026, 8, 2),
            date_depart=datetime.date(2026, 8, 6),
            prix_nuit_snapshot=Decimal('500'),
            statut=Reservation.Statut.TERMINEE,
        )
        # Annulée : ne compte NI dans les nuits vendues NI dans les revenus.
        Reservation.objects.create(
            company=self.co, chambre=self.chambre2,
            date_arrivee=datetime.date(2026, 8, 3),
            date_depart=datetime.date(2026, 8, 5),
            prix_nuit_snapshot=Decimal('800'),
            statut=Reservation.Statut.ANNULEE,
        )
        # No-show : idem, exclue.
        Reservation.objects.create(
            company=self.co, chambre=self.chambre2,
            date_arrivee=datetime.date(2026, 8, 7),
            date_depart=datetime.date(2026, 8, 9),
            prix_nuit_snapshot=Decimal('800'),
            statut=Reservation.Statut.NO_SHOW,
        )

        data = selectors.dashboard_hotellerie(self.co, self.debut, self.fin)

        self.assertEqual(data['nuits_vendues'], 4)
        self.assertEqual(data['revenus_chambres'], Decimal('2000'))
        self.assertEqual(data['nuits_disponibles'], 20)
        self.assertEqual(data['adr'], Decimal('500'))  # 2000 / 4
        self.assertEqual(data['revpar'], Decimal('100'))  # 2000 / 20
        self.assertEqual(data['taux_occupation'], Decimal('0.2'))  # 4 / 20
        # 3 réservations dans la fenêtre, 1 no-show → 1/3.
        self.assertEqual(data['total_reservations'], 3)
        self.assertEqual(data['no_show_count'], 1)
        self.assertAlmostEqual(
            float(data['no_show_rate']), 1 / 3, places=4)

    def test_fenetre_sans_donnees_ne_divise_jamais_par_zero(self):
        data = selectors.dashboard_hotellerie(self.co, self.debut, self.fin)
        self.assertEqual(data['adr'], Decimal('0'))
        self.assertEqual(data['revpar'], Decimal('0'))
        self.assertEqual(data['taux_occupation'], Decimal('0'))
        self.assertEqual(data['no_show_rate'], Decimal('0'))


class DashboardApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-dash-api', 'Hôtel')
        self.user = make_user(self.co, 'hot-dash-api-user')

    def test_default_window_returns_200(self):
        resp = auth(self.user).get('/api/django/hospitality/tableau-bord/')
        self.assertEqual(resp.status_code, 200)
        for key in ('adr', 'revpar', 'taux_occupation', 'no_show_rate'):
            self.assertIn(key, resp.data)

    def test_invalid_date_returns_400(self):
        resp = auth(self.user).get(
            '/api/django/hospitality/tableau-bord/', {'debut': 'nope'})
        self.assertEqual(resp.status_code, 400)
