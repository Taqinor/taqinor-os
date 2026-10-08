"""ASTK98 (C-ASTK-028) — la livraison directe chantier (XPUR23) solde la
réservation du chantier : le matériel reçu et sorti pour le chantier n'est
plus sorti une seconde fois à « Installé ».

Le test part d'un stock libre de 5 (la sonde RESA-1c était masquée par le
plancher ERR80 avec un stock 0). Chantier réservant 10, BCF de livraison
directe de 10 : ENTRÉE 10 + SORTIE 10 à la réception, réservation soldée,
puis `consume_reservations` (« Installé ») ne sort plus rien → stock 5.

Source réelle : `confirm_reception_fournisseur` via l'action `recevoir`,
service chantiers `solder_reservations_vente` (ASTK120),
`consume_reservations` — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_livraison_directe_reservation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, StockReservation
from apps.installations.services import consume_reservations
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, MouvementStock, Produit,
)
from authentication.models import Company

User = get_user_model()


class LivraisonDirecteReservationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK98', slug='astk98-co')
        self.user = User.objects.create_user(
            username='astk98-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client ASTK98', prenom='Test')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ASTK98-1', client=client)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK98', sku='PAN-ASTK98',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'),
            quantite_stock=5)
        self.resa = StockReservation.objects.create(
            company=self.company, installation=self.chantier,
            produit=self.produit, quantite=10)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK98')
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK98-1',
            fournisseur=fournisseur, chantier_livraison=self.chantier,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = self.bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))

    def _recevoir(self):
        return self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{self.bc.id}/'
            'recevoir/',
            {'receptions': [{'ligne': self.ligne.id, 'quantite': 10}]},
            format='json')

    def test_une_seule_sortie(self):
        rep = self._recevoir()
        self.assertEqual(rep.status_code, 200, rep.data)
        # Persistance : réservation relue soldée dès la réception.
        self.resa.refresh_from_db()
        self.assertTrue(self.resa.consomme)
        self.assertEqual(self.resa.quantite, 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)

        # « Installé » : plus aucune sortie pour ce produit.
        consume_reservations(self.chantier, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)
        sorties = MouvementStock.objects.filter(
            produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(sorties.count(), 1)
        self.assertEqual(sorties.get().quantite, 10)

    def test_reliquat_seul_sorti_a_installe(self):
        # Réception partielle de 4 : la réservation garde 6, « Installé »
        # ne sort que le reliquat.
        rep = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{self.bc.id}/'
            'recevoir/',
            {'receptions': [{'ligne': self.ligne.id, 'quantite': 4}]},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.resa.refresh_from_db()
        self.assertFalse(self.resa.consomme)
        self.assertEqual(self.resa.quantite, 6)
