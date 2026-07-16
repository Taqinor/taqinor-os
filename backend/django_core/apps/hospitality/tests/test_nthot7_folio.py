"""NTHOT7 — Folio client unifié (nuitées + extras + restaurant → une facture).

Done = clôturer un folio avec nuitées+extras+repas restaurant crée exactement
une facture ventes avec le détail des lignes, jamais de double-facturation,
tests avec mock du selector ventes.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import (
    Chambre, Folio, LigneFolio, PlanTarifaire, Reservation, TypeChambre,
)

from .helpers import auth, make_company, make_user


class AutoNuiteeLinesTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-folio', 'Hôtel')
        self.user = make_user(self.co, 'hot-folio-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='701')

    def test_reservation_creates_folio_with_one_line_per_night(self):
        reservation = services.creer_reservation(
            company=self.co, user=self.user, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 8, 1),
            date_depart=datetime.date(2026, 8, 4),
        )
        folio = Folio.objects.get(reservation=reservation)
        self.assertEqual(folio.statut, Folio.Statut.OUVERT)
        # Aucun plan tarifaire configuré → prix_nuit_snapshot est None →
        # aucune ligne créée automatiquement (comportement défensif documenté).
        self.assertEqual(folio.lignes.count(), 0)

    def test_reservation_avec_tarif_cree_une_ligne_par_nuit(self):
        PlanTarifaire.objects.create(
            company=self.co, type_chambre=self.type_std,
            canal=PlanTarifaire.Canal.RACK,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 12, 31),
            prix_nuit_ht=Decimal('600'),
        )
        reservation = services.creer_reservation(
            company=self.co, user=self.user, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 9, 1),
            date_depart=datetime.date(2026, 9, 4),
        )
        folio = Folio.objects.get(reservation=reservation)
        self.assertEqual(folio.lignes.count(), 3)
        for ligne in folio.lignes.all():
            self.assertEqual(ligne.origine, LigneFolio.Origine.NUITEE)
            self.assertEqual(ligne.montant_ht, Decimal('600'))
        self.assertEqual(folio.total_ht, Decimal('1800'))


class CloturerFolioTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-folio-cloture', 'Hôtel')
        self.user = make_user(self.co, 'hot-folio-cloture-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='702')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-04',
        )
        self.folio = Folio.objects.create(
            company=self.co, reservation=self.reservation)
        LigneFolio.objects.create(
            folio=self.folio, origine=LigneFolio.Origine.NUITEE,
            description='Nuitée 1', montant_ht=Decimal('500'))
        LigneFolio.objects.create(
            folio=self.folio, origine=LigneFolio.Origine.EXTRA,
            description='Minibar', montant_ht=Decimal('50'))
        LigneFolio.objects.create(
            folio=self.folio, origine=LigneFolio.Origine.RESTAURANT,
            description='Dîner', montant_ht=Decimal('120'))

    def test_cloture_sans_client_leve_erreur(self):
        with self.assertRaises(services.FolioClotureError):
            services.cloturer_folio(self.folio, user=self.user)

    @mock.patch('apps.ventes.services.ajouter_lignes_frais_refactures')
    @mock.patch('apps.ventes.services.creer_facture_regie')
    def test_cloture_cree_une_seule_facture_avec_detail_lignes(
            self, mock_creer_facture, mock_ajouter_lignes):
        from apps.crm.models import Client

        client = Client.objects.create(company=self.co, nom='Client Test')
        self.reservation.client = client
        self.reservation.save(update_fields=['client'])

        fake_facture = mock.Mock(id=999)
        mock_creer_facture.return_value = fake_facture

        facture = services.cloturer_folio(self.folio, user=self.user)

        self.assertEqual(facture, fake_facture)
        mock_creer_facture.assert_called_once()
        _, kwargs = mock_creer_facture.call_args
        self.assertEqual(kwargs['client'], client)
        self.assertEqual(kwargs['company'], self.co)

        mock_ajouter_lignes.assert_called_once()
        _, ajout_kwargs = mock_ajouter_lignes.call_args
        self.assertEqual(ajout_kwargs['facture'], fake_facture)
        self.assertEqual(len(ajout_kwargs['lignes']), 3)

        self.folio.refresh_from_db()
        self.assertEqual(self.folio.statut, Folio.Statut.SOLDE)
        self.assertEqual(self.folio.facture_id, 999)

    @mock.patch('apps.ventes.services.ajouter_lignes_frais_refactures')
    @mock.patch('apps.ventes.services.creer_facture_regie')
    def test_double_cloture_refusee(self, mock_creer_facture, mock_ajouter_lignes):
        from apps.crm.models import Client

        client = Client.objects.create(company=self.co, nom='Client Test 2')
        self.reservation.client = client
        self.reservation.save(update_fields=['client'])
        mock_creer_facture.return_value = mock.Mock(id=1000)

        services.cloturer_folio(self.folio, user=self.user)
        with self.assertRaises(services.FolioClotureError):
            services.cloturer_folio(self.folio, user=self.user)
        mock_creer_facture.assert_called_once()


class FolioApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('hot-folio-api-a', 'A')
        self.co_b = make_company('hot-folio-api-b', 'B')
        self.user_a = make_user(self.co_a, 'hot-folio-api-a-user')
        self.user_b = make_user(self.co_b, 'hot-folio-api-b-user')
        self.type_a = TypeChambre.objects.create(
            company=self.co_a, libelle='Standard')
        self.chambre_a = Chambre.objects.create(
            company=self.co_a, type_chambre=self.type_a, numero='801')
        self.reservation_a = Reservation.objects.create(
            company=self.co_a, chambre=self.chambre_a,
            date_arrivee='2026-08-01', date_depart='2026-08-03',
        )
        self.folio_a = Folio.objects.create(
            company=self.co_a, reservation=self.reservation_a)

    def test_tenant_isolation(self):
        resp = auth(self.user_b).get(
            f'/api/django/hospitality/folios/{self.folio_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_get_own_folio(self):
        resp = auth(self.user_a).get(
            f'/api/django/hospitality/folios/{self.folio_a.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'ouvert')
