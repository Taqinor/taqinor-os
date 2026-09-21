"""Tests NTCON15 — Pénalités de retard calculées PAR LOT.

Couvre : formule XPRJ27 appliquée lot par lot, INDÉPENDANCE entre lots
(un lot en retard n'alourdit pas la pénalité d'un autre), plafond respecté,
retard FIGÉ pour un lot terminé, lot non contractuel → exposition nulle,
et garde d'accès (donnée interne, jamais client) + isolation multi-société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import selectors
from apps.btp_chantier.models import Lot

from .helpers import auth, make_chantier, make_company, make_lot, make_user

PENALITES = '/api/django/btp-chantier/chantiers/{}/penalites-par-lot/'


class PenalitesParLotTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def test_lot_en_retard_expose_sa_propre_penalite(self):
        lot = make_lot(
            self.co, self.chantier, nom='Gros-œuvre', ordre=1,
            jalon_contractuel=True, montant_ht=Decimal('100000.00'),
            taux_penalite_retard_pmil=Decimal('1.500'),
            date_fin_prevue=date(2026, 1, 1))
        data = selectors.penalites_retard_par_lot(
            self.chantier, date_reference=date(2026, 1, 11))
        ligne = data['lots'][0]
        self.assertEqual(ligne['lot_id'], lot.id)
        self.assertTrue(ligne['applicable'])
        self.assertEqual(ligne['jours_depassement'], 10)
        # 10 j × 1,5 ‰ × 100 000 = 1 500,00
        self.assertEqual(ligne['exposition'], Decimal('1500.00'))
        self.assertEqual(data['total_exposition'], Decimal('1500.00'))

    def test_lots_independants_entre_eux(self):
        make_lot(
            self.co, self.chantier, nom='Gros-œuvre', ordre=1,
            jalon_contractuel=True, montant_ht=Decimal('100000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'),
            date_fin_prevue=date(2026, 1, 1))
        make_lot(
            self.co, self.chantier, nom='Électricité', ordre=2,
            jalon_contractuel=True, montant_ht=Decimal('50000.00'),
            taux_penalite_retard_pmil=Decimal('2.000'),
            date_fin_prevue=date(2026, 1, 31))
        data = selectors.penalites_retard_par_lot(
            self.chantier, date_reference=date(2026, 1, 11))
        gros, elec = data['lots']
        # 10 j × 1 ‰ × 100 000 = 1 000 — le lot électricité n'est PAS en
        # retard (échéance au 31/01) : son exposition reste nulle.
        self.assertEqual(gros['exposition'], Decimal('1000.00'))
        self.assertEqual(elec['jours_depassement'], 0)
        self.assertEqual(elec['exposition'], Decimal('0.00'))
        self.assertEqual(data['total_exposition'], Decimal('1000.00'))

    def test_plafond_respecte(self):
        make_lot(
            self.co, self.chantier, nom='CVC', jalon_contractuel=True,
            montant_ht=Decimal('100000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'),
            plafond_penalite_pct=Decimal('0.50'),
            date_fin_prevue=date(2026, 1, 1))
        data = selectors.penalites_retard_par_lot(
            self.chantier, date_reference=date(2026, 3, 1))
        ligne = data['lots'][0]
        # Brute = 59 j × 1 ‰ × 100 000 = 5 900 > plafond 0,5 % = 500.
        self.assertEqual(ligne['exposition_brute'], Decimal('5900.00'))
        self.assertEqual(ligne['plafond_montant'], Decimal('500.00'))
        self.assertEqual(ligne['exposition'], Decimal('500.00'))
        self.assertTrue(ligne['plafonnee'])

    def test_lot_termine_fige_son_retard(self):
        make_lot(
            self.co, self.chantier, nom='Finitions', jalon_contractuel=True,
            montant_ht=Decimal('10000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'),
            date_fin_prevue=date(2026, 1, 1),
            date_fin_reelle=date(2026, 1, 6),
            statut=Lot.Statut.TERMINE)
        data = selectors.penalites_retard_par_lot(
            self.chantier, date_reference=date(2026, 6, 30))
        ligne = data['lots'][0]
        # Le retard s'arrête à la fin RÉELLE : 5 jours, pas 180.
        self.assertEqual(ligne['jours_depassement'], 5)
        self.assertEqual(ligne['exposition'], Decimal('50.00'))

    def test_lot_sans_jalon_contractuel_non_applicable(self):
        make_lot(
            self.co, self.chantier, nom='Peinture', jalon_contractuel=False,
            montant_ht=Decimal('100000.00'),
            taux_penalite_retard_pmil=Decimal('5.000'),
            date_fin_prevue=date(2020, 1, 1))
        data = selectors.penalites_retard_par_lot(
            self.chantier, date_reference=date(2026, 1, 11))
        ligne = data['lots'][0]
        self.assertFalse(ligne['applicable'])
        self.assertEqual(ligne['exposition'], Decimal('0'))
        self.assertEqual(data['total_exposition'], Decimal('0'))

    def test_endpoint_expose_le_calcul(self):
        make_lot(
            self.co, self.chantier, nom='Gros-œuvre', jalon_contractuel=True,
            montant_ht=Decimal('100000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'),
            date_fin_prevue=date(2026, 1, 1),
            date_fin_reelle=date(2026, 1, 11),
            statut=Lot.Statut.TERMINE)
        resp = auth(self.user).get(PENALITES.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(len(resp.data['lots']), 1)
        self.assertEqual(
            Decimal(resp.data['lots'][0]['exposition']), Decimal('1000.00'))

    def test_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = auth(self.user).get(PENALITES.format(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_role_normal_refuse(self):
        # Donnée interne : un rôle « normal » (lecture BTP) n'y accède pas.
        lecteur = make_user(self.co, role='normal')
        resp = auth(lecteur).get(PENALITES.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
