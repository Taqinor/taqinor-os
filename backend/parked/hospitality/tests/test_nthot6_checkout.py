"""NTHOT6 — Check-out et libération de chambre.

Done = un check-out avec solde impayé est refusé sauf override tracé, la
chambre passe automatiquement en statut "à nettoyer", tests.
"""
from decimal import Decimal

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import Chambre, Folio, LigneFolio, Reservation, TypeChambre

from .helpers import auth, make_company, make_user


class CheckOutServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-checkout', 'Hôtel')
        self.admin = make_user(self.co, 'hot-checkout-admin', role='admin')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='901')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-03',
            statut=Reservation.Statut.EN_COURS,
        )
        self.chambre.statut = Chambre.Statut.OCCUPEE
        self.chambre.save(update_fields=['statut'])
        self.folio = Folio.objects.create(
            company=self.co, reservation=self.reservation)
        LigneFolio.objects.create(
            folio=self.folio, origine=LigneFolio.Origine.NUITEE,
            description='Nuitée', montant_ht=Decimal('500'))

    def test_check_out_refuse_si_folio_non_solde(self):
        with self.assertRaises(services.CheckOutError):
            services.check_out(self.reservation, user=self.admin)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.Statut.EN_COURS)

    def test_check_out_avec_override_journalise_et_procede(self):
        services.check_out(self.reservation, user=self.admin, override=True)
        self.reservation.refresh_from_db()
        self.chambre.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.Statut.TERMINEE)
        self.assertEqual(self.chambre.statut, Chambre.Statut.SALE)

        from apps.audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(
                company=self.co, detail__icontains='forcé').exists())

    def test_check_out_avec_folio_solde_procede_sans_override(self):
        self.folio.statut = Folio.Statut.SOLDE
        self.folio.save(update_fields=['statut'])
        services.check_out(self.reservation, user=self.admin)
        self.reservation.refresh_from_db()
        self.chambre.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.Statut.TERMINEE)
        self.assertEqual(self.chambre.statut, Chambre.Statut.SALE)

    def test_check_out_refuse_si_reservation_pas_en_cours(self):
        self.reservation.statut = Reservation.Statut.CONFIRMEE
        self.reservation.save(update_fields=['statut'])
        with self.assertRaises(services.CheckOutError):
            services.check_out(self.reservation, user=self.admin)


class CheckOutApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-checkout-api', 'Hôtel')
        self.user = make_user(self.co, 'hot-checkout-api-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='902')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-03',
            statut=Reservation.Statut.EN_COURS,
        )
        Folio.objects.create(company=self.co, reservation=self.reservation)

    def _url(self):
        return f'/api/django/hospitality/reservations/{self.reservation.pk}/check-out/'

    def test_check_out_sans_folio_ligne_procede(self):
        # Folio existant mais sans lignes → total 0, considéré non « soldé »
        # explicitement (statut ouvert) → refusé sans override.
        resp = auth(self.user).post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_check_out_override_refuse_pour_role_non_responsable(self):
        normal = make_user(self.co, 'hot-checkout-normal', role='normal')
        resp = auth(normal).post(
            self._url(), {'override': True}, format='json')
        self.assertEqual(resp.status_code, 403)
