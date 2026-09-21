"""NTHOT3 — Réservations (walk-in/téléphone/email).

Done = une tentative de double-réservation sur la même chambre/dates est
refusée, tests.
"""
from django.test import TestCase

from apps.hospitality.models import Chambre, Reservation, TypeChambre

from .helpers import auth, make_company, make_user, rows


class ReservationApiTests(TestCase):
    BASE = '/api/django/hospitality/reservations/'

    def setUp(self):
        self.co_a = make_company('hot-res-a', 'A')
        self.co_b = make_company('hot-res-b', 'B')
        self.user_a = make_user(self.co_a, 'hot-res-a-user')
        self.user_b = make_user(self.co_b, 'hot-res-b-user')
        self.type_a = TypeChambre.objects.create(
            company=self.co_a, libelle='Standard')
        self.chambre_a = Chambre.objects.create(
            company=self.co_a, type_chambre=self.type_a, numero='101')

    def _payload(self, **overrides):
        data = {
            'chambre': self.chambre_a.id,
            'date_arrivee': '2026-08-01',
            'date_depart': '2026-08-05',
            'nb_adultes': 2,
            'origine': 'walk_in',
            'client_nom': 'Client Test',
        }
        data.update(overrides)
        return data

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        reservation = Reservation.objects.get(id=resp.data['id'])
        self.assertEqual(reservation.company, self.co_a)
        self.assertEqual(reservation.statut, Reservation.Statut.CONFIRMEE)

    def test_double_reservation_same_chambre_dates_refusee(self):
        api = auth(self.user_a)
        resp1 = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)
        # Chevauchement partiel des dates → refusé.
        resp2 = api.post(
            self.BASE,
            self._payload(date_arrivee='2026-08-03', date_depart='2026-08-07'),
            format='json',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('chambre', resp2.data)
        self.assertEqual(
            Reservation.objects.filter(chambre=self.chambre_a).count(), 1)

    def test_non_overlapping_dates_allowed(self):
        api = auth(self.user_a)
        resp1 = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)
        resp2 = api.post(
            self.BASE,
            self._payload(date_arrivee='2026-08-05', date_depart='2026-08-08'),
            format='json',
        )
        self.assertEqual(resp2.status_code, 201, resp2.data)

    def test_tenant_isolation(self):
        Reservation.objects.create(
            company=self.co_a, chambre=self.chambre_a,
            date_arrivee='2026-08-01', date_depart='2026-08-05',
        )
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_filter_by_statut_and_date_arrivee(self):
        api = auth(self.user_a)
        api.post(self.BASE, self._payload(), format='json')
        resp = api.get(
            self.BASE,
            {'statut': 'confirmee', 'date_arrivee': '2026-08-01'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)
        resp_empty = api.get(self.BASE, {'date_arrivee': '2026-09-01'})
        self.assertEqual(len(rows(resp_empty)), 0)
