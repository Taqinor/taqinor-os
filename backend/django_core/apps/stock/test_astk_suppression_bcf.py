"""ASTK84 — un BCF hors brouillon, reçu ou facturé ne se supprime plus.

Rejoue BCF-14 (audit stock 06/10/2026, rouge sur 3c7b29427) : DELETE d'un BCF
reçu = 204, average_cost 100.00 → 60.00 (l'historique de coût disparaît) et
facture.bon_commande_id = None.

Source réelle : `BonCommandeFournisseurViewSet.perform_destroy` + `average_cost`
réels, via l'API (aucun mock).

Run :
    python manage.py test apps.stock.test_astk_suppression_bcf -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services import average_cost
from authentication.models import Company

User = get_user_model()

URL = '/api/django/stock/bons-commande-fournisseur/'
MSG = 'Bon de commande reçu ou facturé : suppression refusée (annulez-le).'


class SuppressionBcfTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK84', slug='astk84-co')
        self.admin = User.objects.create_user(
            username='astk84-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK84')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK84', sku='ASTK84-1',
            prix_vente=Decimal('150'), prix_achat=Decimal('60'),
            quantite_stock=0)

    def _bcf(self, statut, reference):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur, statut=statut)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        return bc, ligne

    def test_bcf_recu_non_supprimable(self):
        bc, ligne = self._bcf(BonCommandeFournisseur.Statut.ENVOYE,
                              'BCF-ASTK84-1')
        rep = self.api.post(f'{URL}{bc.pk}/recevoir/', {
            'receptions': [{'ligne': ligne.pk, 'quantite': 10}]},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.produit.refresh_from_db()
        self.assertEqual(average_cost(self.produit), Decimal('100.00'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK84-1',
            fournisseur=self.fournisseur, bon_commande=bc,
            date_facture=datetime.date(2026, 9, 1),
            montant_ttc=Decimal('1200'))
        avant = self.api.get(f'{URL}{bc.pk}/').data

        rep = self.api.delete(f'{URL}{bc.pk}/')
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertIn(MSG, str(rep.data))
        self.assertTrue(BonCommandeFournisseur.objects.filter(
            pk=bc.pk).exists())
        self.produit.refresh_from_db()
        self.assertEqual(average_cost(self.produit), Decimal('100.00'))
        facture.refresh_from_db()
        self.assertEqual(facture.bon_commande_id, bc.pk)
        self.assertEqual(self.api.get(f'{URL}{bc.pk}/').data, avant)

    def test_bcf_facture_brouillon_non_supprimable(self):
        bc, _ligne = self._bcf(BonCommandeFournisseur.Statut.BROUILLON,
                               'BCF-ASTK84-2')
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK84-2',
            fournisseur=self.fournisseur, bon_commande=bc,
            date_facture=datetime.date(2026, 9, 1),
            montant_ttc=Decimal('1200'))
        rep = self.api.delete(f'{URL}{bc.pk}/')
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertTrue(BonCommandeFournisseur.objects.filter(
            pk=bc.pk).exists())

    def test_bcf_hors_brouillon_non_supprimable(self):
        for statut, ref in ((BonCommandeFournisseur.Statut.ENVOYE, 'E'),
                            (BonCommandeFournisseur.Statut.ANNULE, 'A')):
            bc, _ligne = self._bcf(statut, f'BCF-ASTK84-{ref}')
            rep = self.api.delete(f'{URL}{bc.pk}/')
            self.assertEqual(rep.status_code, 400, (statut, rep.data))
            self.assertTrue(BonCommandeFournisseur.objects.filter(
                pk=bc.pk).exists())

    def test_bcf_brouillon_vierge_supprimable(self):
        bc, _ligne = self._bcf(BonCommandeFournisseur.Statut.BROUILLON,
                               'BCF-ASTK84-3')
        rep = self.api.delete(f'{URL}{bc.pk}/')
        self.assertEqual(rep.status_code, 204)
        self.assertFalse(BonCommandeFournisseur.objects.filter(
            pk=bc.pk).exists())
