"""Tests NTCON11 — Comparatif déboursé sec vs facturé par chantier.

Couvre : main-d'œuvre (timesheet) + sous-traitance (OrdreSousTraitance) +
matériel (StockReservation consommée × Produit.prix_achat), agrégés
correctement sur un chantier de test ; admin/responsable only.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import AvenantChantier

from .helpers import (
    auth, make_chantier, make_company, make_fournisseur,
    make_ligne_situation, make_ordre_sous_traitance, make_produit,
    make_projet_lie, make_reservation_stock, make_ressource_profil,
    make_situation, make_timesheet, make_user,
)

BASE = '/api/django/btp-chantier/chantiers/{}/debourse-vs-facture/'


class DebourseVsFactureTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

        # ── Main-d'œuvre ────────────────────────────────────────────────
        self.projet = make_projet_lie(self.co, self.chantier)
        ressource = make_ressource_profil(self.co)
        make_timesheet(self.co, self.projet, ressource, cout=Decimal('4000.00'))
        # Timesheet NON facturable -> ne doit jamais compter.
        make_timesheet(
            self.co, self.projet, ressource, cout=Decimal('999.00'),
            facturable=False)

        # ── Sous-traitance ──────────────────────────────────────────────
        fournisseur = make_fournisseur(self.co)
        make_ordre_sous_traitance(
            self.co, self.chantier, fournisseur,
            montant=Decimal('6000.00'), montant_realise=Decimal('5500.00'))

        # ── Matériel ─────────────────────────────────────────────────────
        produit = make_produit(self.co, prix_achat=Decimal('100.00'))
        make_reservation_stock(
            self.co, self.chantier, produit, quantite=10, consomme=True)
        # Réservation NON consommée -> ne doit jamais compter. Produit
        # DISTINCT : StockReservation porte une contrainte unique
        # (installation, produit) — réutiliser le même produit percuterait
        # cette contrainte plutôt que de tester le filtre consomme=False.
        produit_non_consomme = make_produit(self.co, prix_achat=Decimal('50.00'))
        make_reservation_stock(
            self.co, self.chantier, produit_non_consomme, quantite=999,
            consomme=False)

        # ── Facturé ──────────────────────────────────────────────────────
        situation = make_situation(self.co, self.projet, numero=1)
        make_ligne_situation(
            self.co, situation, montant_periode=Decimal('12000.00'))
        AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-N11-0001', description='Avenant',
            montant_ht=Decimal('2000.00'),
            statut=AvenantChantier.Statut.APPROUVE)

    def test_comparatif_correct(self):
        api = auth(self.user)
        resp = api.get(BASE.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        data = resp.data
        self.assertEqual(Decimal(data['main_oeuvre']), Decimal('4000.00'))
        self.assertEqual(Decimal(data['sous_traitance']), Decimal('5500.00'))
        self.assertEqual(Decimal(data['materiel']), Decimal('1000.00'))
        self.assertEqual(
            Decimal(data['debourse_sec_total']),
            Decimal('4000.00') + Decimal('5500.00') + Decimal('1000.00'))
        self.assertEqual(
            Decimal(data['situations_facturees']), Decimal('12000.00'))
        self.assertEqual(Decimal(data['avenants_approuves']), Decimal('2000.00'))
        self.assertEqual(
            Decimal(data['facture_total']),
            Decimal('12000.00') + Decimal('2000.00'))

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        api = auth(self.user)
        resp = api.get(BASE.format(other_chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
