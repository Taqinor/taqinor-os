"""Groupe ASTK — réservations de chantier : réception, BC, arrondi, retour.

Sondes RESA de l'audit stock du 2026-10-06 rejouées sur les services réels
(aucun mock) :
  * ASTK121 (RESA-2) — la réception d'un BCF « besoin chantier » ne fait que
    COMPLÉTER la réservation, jamais la réduire.

Run :
    python manage.py test apps.installations.tests_astk_reservations_reception
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, InstallationActivity, StockReservation,
)
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    available_quantity, confirm_reception_fournisseur,
    draft_bcf_for_shortfall,
)
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

_seq = itertools.count(1)


class ResaBase(TestCase):
    SLUG = 'co-astk-resa'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.SLUG, defaults={'nom': 'Co ASTK RESA'})
        self.user = User.objects.create_user(
            username=f'resp-{self.SLUG}', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ASTK RESA')

    def produit(self, nom, stock):
        n = next(_seq)
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'SKU-ASTKRESA-{n}',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'),
            quantite_stock=stock)

    def devis_accepte(self, lignes):
        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'astkresa-{n}@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTKRESA-{n}',
            client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        for produit, qte in lignes:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
        return devis

    def chantier(self, lignes):
        devis = self.devis_accepte(lignes)
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        return inst

    def resa(self, inst, produit):
        return StockReservation.objects.get(
            installation=inst, produit=produit)

    def confirmer_reception(self, bc, produit, qte):
        n = next(_seq)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTKRESA-{n}',
            bon_commande=bc, created_by=self.user)
        rec.lignes.create(
            ligne_commande=bc.lignes.get(produit=produit), produit=produit,
            quantite=qte)
        confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        return rec

    def bcf_du_manque(self, inst):
        bon, _ = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])
        return bon

    def installer(self, inst):
        changer_statut_chantier(
            inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)
        inst.refresh_from_db()


class ReceptionNeReduitPasTests(ResaBase):
    SLUG = 'co-astk121'

    def test_reception_complete_jamais_ne_reduit(self):
        panneau = self.produit('Panneau ASTK121', stock=5)
        inst = self.chantier([(panneau, 20)])
        self.assertEqual(self.resa(inst, panneau).quantite, 20)
        bon = self.bcf_du_manque(inst)
        self.confirmer_reception(bon, panneau, 10)

        resa = self.resa(inst, panneau)
        self.assertEqual((resa.quantite, resa.active), (20, True))
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 15)
        self.assertEqual(available_quantity(panneau), -5)

        self.installer(inst)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 0)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=inst, kind=InstallationActivity.Kind.NOTE,
            body__contains='manque 5').exists())
