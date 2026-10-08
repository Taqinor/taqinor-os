"""ASTK135 (C-ASTK-028) — « une vente = une sortie » côté facturation.

Sonde RESA-1 : devis de 10 panneaux accepté (chantier, réservation 10, stock
30). La facture directe sortait 10 (stock 20) sans solder la réservation du
chantier ; « Installé » ressortait 10 (stock 10). Même mécanisme pour la
livraison d'un BC toggle OFF (`marquer-livre`). Après ASTK135, la sortie de la
vente SOLDE la réservation (service chantiers ASTK120) dans la même
transaction. Aucun mock : services réels, endpoint réel.

Run :
    python manage.py test apps.ventes.tests.test_facture_astk_sortie_unique
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, StockReservation
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_sortie
from apps.ventes.domain.facturation_ops import facturer_devis_complet
from apps.ventes.models import BonCommande, Devis, LigneDevis

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class FactureSortieUniqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Co ASTK135', slug=f'co-astk135-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'resp-astk135-{_nxt()}', password='x',
            company=self.company, role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK135',
            sku=f'SKU-ASTK135-{_nxt()}', prix_vente=Decimal('100'),
            quantite_stock=30, tva=Decimal('20.00'))
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'astk135-{_nxt()}@example.invalid')

    def _devis(self):
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK135-{_nxt()}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        return devis, inst

    def _installer(self, inst):
        changer_statut_chantier(
            inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)

    def _sorties(self):
        return MouvementStock.objects.filter(
            produit=self.panneau, type_mouvement=mouvement_type_sortie())

    def _assert_une_sortie(self, inst, reference):
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        sorties = self._sorties()
        self.assertEqual(
            sorties.aggregate(t=Sum('quantite'))['t'], 10)
        self.assertEqual(list(sorties.values_list('reference', flat=True)),
                         [reference])
        resa = StockReservation.objects.get(
            installation=inst, produit=self.panneau)
        self.assertTrue(resa.consomme)

    def test_facture_directe_puis_installe_une_sortie(self):
        devis, inst = self._devis()
        self.assertEqual(StockReservation.objects.get(
            installation=inst, produit=self.panneau).quantite, 10)
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self._installer(inst)
        self._assert_une_sortie(inst, devis.reference)

    def test_bc_livre_toggle_off_puis_installe_une_sortie(self):
        devis, inst = self._devis()
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ASTK135-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self._installer(inst)
        self._assert_une_sortie(inst, bc.reference)

    def test_devis_sans_chantier_inchange(self):
        lead = Lead.objects.create(
            company=self.company, nom='Sans', prenom='Chantier',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK135-{_nxt()}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._sorties().count(), 1)
