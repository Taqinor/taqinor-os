"""NTHOT8 — Taxe de séjour paramétrable.

Done = une réservation de 3 nuits/2 adultes/1 enfant avec exonération enfants
calcule la taxe exacte, désactivée = aucune ligne ajoutée, tests.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import (
    Chambre, Folio, LigneFolio, ParametresTaxeSejour, Reservation,
    TypeChambre,
)

from .helpers import make_company, make_user


class CalculerTaxeSejourTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-taxe', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1001')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-04',  # 3 nuits
            nb_adultes=2, nb_enfants=1,
        )

    def test_aucun_parametre_configure_renvoie_zero(self):
        self.assertEqual(
            services.calculer_taxe_sejour(self.reservation), Decimal('0'))

    def test_3_nuits_2_adultes_1_enfant_exoneration_enfants(self):
        ParametresTaxeSejour.objects.create(
            company=self.co,
            montant_par_nuit_par_personne=Decimal('20'),
            exoneration_enfants=True,
            actif=True,
        )
        # 3 nuits × 2 adultes (enfant exonéré) × 20 = 120.
        self.assertEqual(
            services.calculer_taxe_sejour(self.reservation), Decimal('120'))

    def test_sans_exoneration_enfants_compte_dans_le_total(self):
        ParametresTaxeSejour.objects.create(
            company=self.co,
            montant_par_nuit_par_personne=Decimal('20'),
            exoneration_enfants=False,
            actif=True,
        )
        # 3 nuits × 3 personnes × 20 = 180.
        self.assertEqual(
            services.calculer_taxe_sejour(self.reservation), Decimal('180'))

    def test_desactivee_ne_calcule_rien(self):
        ParametresTaxeSejour.objects.create(
            company=self.co,
            montant_par_nuit_par_personne=Decimal('20'),
            actif=False,
        )
        self.assertEqual(
            services.calculer_taxe_sejour(self.reservation), Decimal('0'))


class ClotureAvecTaxeSejourTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-taxe-cloture', 'Hôtel')
        self.user = make_user(self.co, 'hot-taxe-cloture-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1002')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-04',
            nb_adultes=2, nb_enfants=1,
        )
        self.folio = Folio.objects.create(
            company=self.co, reservation=self.reservation)
        LigneFolio.objects.create(
            folio=self.folio, origine=LigneFolio.Origine.NUITEE,
            description='Nuitées', montant_ht=Decimal('1500'))

        from apps.crm.models import Client
        self.client_crm = Client.objects.create(company=self.co, nom='Client')
        self.reservation.client = self.client_crm
        self.reservation.save(update_fields=['client'])

    @mock.patch('apps.ventes.services.ajouter_lignes_frais_refactures')
    @mock.patch('apps.ventes.services.creer_facture_regie')
    def test_cloture_ajoute_ligne_taxe_sejour_active(
            self, mock_creer_facture, mock_ajouter_lignes):
        ParametresTaxeSejour.objects.create(
            company=self.co,
            montant_par_nuit_par_personne=Decimal('20'),
            exoneration_enfants=True, actif=True,
        )
        mock_creer_facture.return_value = mock.Mock(id=1)
        services.cloturer_folio(self.folio, user=self.user)
        self.assertTrue(
            self.folio.lignes.filter(
                origine=LigneFolio.Origine.TAXE_SEJOUR,
                montant_ht=Decimal('120'),
            ).exists())

    @mock.patch('apps.ventes.services.ajouter_lignes_frais_refactures')
    @mock.patch('apps.ventes.services.creer_facture_regie')
    def test_cloture_sans_parametre_najoute_aucune_ligne_taxe(
            self, mock_creer_facture, mock_ajouter_lignes):
        mock_creer_facture.return_value = mock.Mock(id=2)
        services.cloturer_folio(self.folio, user=self.user)
        self.assertFalse(
            self.folio.lignes.filter(
                origine=LigneFolio.Origine.TAXE_SEJOUR).exists())
