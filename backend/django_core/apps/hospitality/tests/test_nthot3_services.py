"""NTHOT3 — services.creer_reservation / check_reservation_overlap (unitaire).

Complète test_nthot3_reservations.py (couche API) par des tests directs sur
la couche service, notamment la résolution client (mockée — jamais un import
direct de apps.crm.models)."""
import datetime
from unittest import mock

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import Chambre, Reservation, TypeChambre

from .helpers import make_company, make_user


class CheckReservationOverlapTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-res-svc', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='201')

    def test_no_chambre_is_noop(self):
        # Aucune exception : une réservation sur type de chambre seul (pas
        # encore assignée) ne peut pas chevaucher.
        services.check_reservation_overlap(
            None, datetime.date(2026, 8, 1), datetime.date(2026, 8, 5))

    def test_overlap_raises(self):
        Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 8, 1),
            date_depart=datetime.date(2026, 8, 5),
        )
        with self.assertRaises(services.ReservationOverlapError):
            services.check_reservation_overlap(
                self.chambre,
                datetime.date(2026, 8, 4), datetime.date(2026, 8, 6))

    def test_annulee_does_not_block(self):
        Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 8, 1),
            date_depart=datetime.date(2026, 8, 5),
            statut=Reservation.Statut.ANNULEE,
        )
        # Ne lève pas : une réservation annulée ne bloque jamais.
        services.check_reservation_overlap(
            self.chambre,
            datetime.date(2026, 8, 3), datetime.date(2026, 8, 6))


class ResolveClientReservationTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-res-client', 'Hôtel')

    @mock.patch('apps.crm.selectors.find_client_by_phone')
    @mock.patch('apps.crm.selectors.find_client_by_email')
    def test_resolves_by_phone_when_no_email_match(self, by_email, by_phone):
        by_email.return_value = None
        sentinel_client = mock.Mock()
        by_phone.return_value = sentinel_client
        result = services.resolve_client_reservation(
            self.co, telephone='0600000000')
        self.assertIs(result, sentinel_client)

    def test_no_match_returns_none(self):
        result = services.resolve_client_reservation(
            self.co, telephone='0600000000')
        self.assertIsNone(result)


class CreerReservationTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-res-creer', 'Hôtel')
        self.user = make_user(self.co, 'hot-res-creer-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='301')

    def test_creer_reservation_sets_created_by_and_company(self):
        reservation = services.creer_reservation(
            company=self.co, user=self.user, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 9, 1),
            date_depart=datetime.date(2026, 9, 3),
            client_nom='Client Direct',
        )
        self.assertEqual(reservation.company, self.co)
        self.assertEqual(reservation.created_by, self.user)
        self.assertEqual(reservation.statut, Reservation.Statut.CONFIRMEE)

    def test_creer_reservation_raises_on_overlap(self):
        services.creer_reservation(
            company=self.co, user=self.user, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 9, 1),
            date_depart=datetime.date(2026, 9, 3),
        )
        with self.assertRaises(services.ReservationOverlapError):
            services.creer_reservation(
                company=self.co, user=self.user, chambre=self.chambre,
                date_arrivee=datetime.date(2026, 9, 2),
                date_depart=datetime.date(2026, 9, 4),
            )
