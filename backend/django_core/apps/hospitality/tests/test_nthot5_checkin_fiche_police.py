"""NTHOT5 — Check-in avec fiche de police marocaine imprimable.

Done = un check-in sans fiche client complète est bloqué, le PDF fiche de
police s'imprime avec tous les champs requis, tests.
"""
from unittest import mock

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import Chambre, FicheClient, Reservation, TypeChambre
from apps.hospitality.pdf import render_fiche_police_html

from .helpers import auth, make_company, make_user


FICHE_OK = {
    'nom_complet': 'Jean Dupont',
    'nationalite': 'Française',
    'type_piece': 'passeport',
    'numero_piece': 'X1234567',
    'date_naissance': '1985-04-12',
}


class CheckInServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-checkin', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='401')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-05',
        )

    def test_check_in_sans_fiche_est_bloque(self):
        with self.assertRaises(services.CheckInError):
            services.check_in(self.reservation, fiches_data=[])
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.Statut.CONFIRMEE)

    def test_check_in_fiche_incomplete_est_bloque(self):
        incomplete = dict(FICHE_OK)
        incomplete.pop('numero_piece')
        with self.assertRaises(services.CheckInError):
            services.check_in(self.reservation, fiches_data=[incomplete])
        self.assertEqual(FicheClient.objects.count(), 0)
        self.chambre.refresh_from_db()
        self.assertEqual(self.chambre.statut, Chambre.Statut.LIBRE)

    def test_check_in_complet_passe_chambre_occupee_et_reservation_en_cours(self):
        services.check_in(self.reservation, fiches_data=[FICHE_OK])
        self.reservation.refresh_from_db()
        self.chambre.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.Statut.EN_COURS)
        self.assertEqual(self.chambre.statut, Chambre.Statut.OCCUPEE)
        self.assertEqual(self.reservation.fiches_client.count(), 1)

    def test_check_in_assigns_free_chambre_when_none_set(self):
        chambre_libre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='402')
        reservation = Reservation.objects.create(
            company=self.co, type_chambre=self.type_std,
            date_arrivee='2026-08-01', date_depart='2026-08-05',
        )
        services.check_in(reservation, fiches_data=[FICHE_OK])
        reservation.refresh_from_db()
        self.assertIn(
            reservation.chambre_id, {self.chambre.id, chambre_libre.id})
        self.assertEqual(reservation.chambre.statut, Chambre.Statut.OCCUPEE)


class CheckInApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-checkin-api', 'Hôtel')
        self.user = make_user(self.co, 'hot-checkin-api-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='501')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-05',
        )

    def _url(self, suffix):
        return f'/api/django/hospitality/reservations/{self.reservation.pk}/{suffix}/'

    def test_check_in_missing_fiches_returns_400(self):
        resp = auth(self.user).post(self._url('check-in'), {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_check_in_success_returns_200(self):
        resp = auth(self.user).post(
            self._url('check-in'), {'fiches': [FICHE_OK]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')


class FichePoliceHtmlTests(TestCase):
    """PDF fiche de police — vérifie le HTML source (le rendu WeasyPrint réel
    est testé côté core.pdf ; ce test vérifie que TOUS les champs requis
    apparaissent dans le document)."""

    def setUp(self):
        self.co = make_company('hot-fiche-pdf', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='601')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-05',
        )
        services.check_in(self.reservation, fiches_data=[FICHE_OK])
        self.reservation.refresh_from_db()

    def test_html_contains_all_required_fields(self):
        html = render_fiche_police_html(self.reservation)
        self.assertIn('Jean Dupont', html)
        self.assertIn('Française', html)
        self.assertIn('Passeport', html)
        self.assertIn('X1234567', html)
        self.assertIn('1985-04-12', html)
        self.assertIn('601', html)

    @mock.patch('apps.hospitality.pdf.render_pdf')
    def test_render_pdf_calls_shared_service(self, mock_render_pdf):
        mock_render_pdf.return_value = b'%PDF-fake'
        from apps.hospitality.pdf import render_fiche_police_pdf
        result = render_fiche_police_pdf(self.reservation)
        self.assertEqual(result, b'%PDF-fake')
        mock_render_pdf.assert_called_once()
