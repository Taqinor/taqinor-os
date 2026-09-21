"""NTHOT20 — Petit-déjeuner / pension tracking.

Done = un repas inclus en pension complète n'est pas refacturé au folio si
pointé comme consommé, un repas hors formule reste facturable normalement,
tests.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import (
    Chambre, Folio, LigneFolio, Reservation, TicketPension, TypeChambre,
)

from .helpers import make_company, make_user

FICHE = {
    'nom_complet': 'Jean Test', 'nationalite': 'Française',
    'type_piece': 'passeport', 'numero_piece': 'X123', 'date_naissance': '1990-01-01',
}


class GenerationTicketsPensionTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-pension', 'Hôtel')
        self.user = make_user(self.co, 'hot-pension-user')
        self.type_std = TypeChambre.objects.create(company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='101')

    def _make_reservation(self, formule):
        return Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 8, 1),
            date_depart=datetime.date(2026, 8, 4),
            formule_pension=formule,
        )

    def test_check_in_pension_complete_genere_3_repas_par_jour(self):
        reservation = self._make_reservation(Reservation.FormulePension.PENSION_COMPLETE)
        services.check_in(reservation, fiches_data=[FICHE], user=self.user)
        tickets = TicketPension.objects.filter(reservation=reservation)
        # 3 nuits × 3 repas = 9 tickets.
        self.assertEqual(tickets.count(), 9)
        self.assertEqual(
            tickets.filter(type_repas='petit_dejeuner').count(), 3)
        self.assertEqual(tickets.filter(type_repas='dejeuner').count(), 3)
        self.assertEqual(tickets.filter(type_repas='diner').count(), 3)

    def test_check_in_demi_pension_genere_petit_dej_et_diner(self):
        reservation = self._make_reservation(Reservation.FormulePension.DEMI_PENSION)
        services.check_in(reservation, fiches_data=[FICHE], user=self.user)
        tickets = TicketPension.objects.filter(reservation=reservation)
        self.assertEqual(tickets.count(), 6)
        self.assertEqual(tickets.filter(type_repas='dejeuner').count(), 0)

    def test_check_in_sans_formule_ne_genere_aucun_ticket(self):
        reservation = self._make_reservation(Reservation.FormulePension.AUCUNE)
        services.check_in(reservation, fiches_data=[FICHE], user=self.user)
        self.assertEqual(
            TicketPension.objects.filter(reservation=reservation).count(), 0)

    def test_check_in_idempotent_ne_double_pas_les_tickets(self):
        reservation = self._make_reservation(Reservation.FormulePension.PETIT_DEJEUNER)
        services._generer_tickets_pension(reservation)
        services._generer_tickets_pension(reservation)
        self.assertEqual(
            TicketPension.objects.filter(reservation=reservation).count(), 3)


class PointerRepasOuFacturerTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-pension-fact', 'Hôtel')
        self.user = make_user(self.co, 'hot-pension-fact-user')
        self.type_std = TypeChambre.objects.create(company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='201')
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee=datetime.date(2026, 8, 1),
            date_depart=datetime.date(2026, 8, 4),
            formule_pension=Reservation.FormulePension.PENSION_COMPLETE,
        )
        Folio.objects.create(company=self.co, reservation=self.reservation)
        services.check_in(self.reservation, fiches_data=[FICHE], user=self.user)

    def test_repas_inclus_pointe_nest_jamais_refacture(self):
        nb_lignes_avant = LigneFolio.objects.filter(
            folio__reservation=self.reservation).count()
        result = services.pointer_repas_ou_facturer(
            self.reservation, date_repas=datetime.date(2026, 8, 1),
            type_repas='dejeuner', montant_ht=Decimal('150'))
        self.assertIsInstance(result, TicketPension)
        self.assertTrue(result.consomme)
        nb_lignes_apres = LigneFolio.objects.filter(
            folio__reservation=self.reservation).count()
        self.assertEqual(nb_lignes_avant, nb_lignes_apres)

    def test_meme_repas_pointe_deux_fois_ne_facture_pas_la_seconde_fois(self):
        services.pointer_repas_ou_facturer(
            self.reservation, date_repas=datetime.date(2026, 8, 1),
            type_repas='dejeuner', montant_ht=Decimal('150'))
        nb_lignes_avant = LigneFolio.objects.filter(
            folio__reservation=self.reservation).count()
        result = services.pointer_repas_ou_facturer(
            self.reservation, date_repas=datetime.date(2026, 8, 1),
            type_repas='dejeuner', montant_ht=Decimal('150'))
        # Le ticket est déjà consommé : la seconde tentative retombe sur un
        # repas « hors formule » (crée une ligne facturable), jamais un
        # double-pointage silencieux du même ticket.
        self.assertIsInstance(result, LigneFolio)
        nb_lignes_apres = LigneFolio.objects.filter(
            folio__reservation=self.reservation).count()
        self.assertEqual(nb_lignes_apres, nb_lignes_avant + 1)

    def test_repas_hors_formule_reste_facturable_normalement(self):
        # Réservation en pension complète : un 4ème dîner (hors séjour) n'a
        # pas de ticket correspondant → facturé normalement.
        result = services.pointer_repas_ou_facturer(
            self.reservation, date_repas=datetime.date(2026, 8, 10),
            type_repas='diner', montant_ht=Decimal('200'),
            description='Dîner supplémentaire')
        self.assertIsInstance(result, LigneFolio)
        self.assertEqual(result.montant_ht, Decimal('200'))
        self.assertEqual(result.origine, LigneFolio.Origine.RESTAURANT)
