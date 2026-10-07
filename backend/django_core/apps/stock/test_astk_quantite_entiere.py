"""ASTK45 (C-ASTK-009) — une quantité de consommation non entière est refusée.

Constat MVT-13 : un kit dont un composant consomme 0,5 m de câble, assemblé
3 fois, consommait 1,5 m → la colonne entière du mouvement tronquait en
silence (mouvement quantite=1, avant=10, après=8 : le stock baissait de 2).
Désormais `consommer_et_produire_assemblage` et `record_stock_movement`
lèvent une ValidationError lisible et n'écrivent rien.

Run :
    python manage.py test apps.stock.test_astk_quantite_entiere
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from authentication.models import Company
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import (
    consommer_et_produire_assemblage, mouvement_type_sortie,
    record_stock_movement,
)

User = get_user_model()


class QuantiteEntiereTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK45 Co', slug='astk45-co')
        self.user = User.objects.create_user(
            username='astk45-user', password='x', company=self.company,
            role_legacy='admin')
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble 6 mm²', sku='CAB-ASTK45',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            quantite_stock=10)
        self.composite = Produit.objects.create(
            company=self.company, nom='Kit câblage ASTK45', sku='KIT-ASTK45',
            prix_vente=Decimal('200'), prix_achat=Decimal('0'),
            quantite_stock=0)

    def _assembler(self, quantite_par_kit, quantite_produite):
        return consommer_et_produire_assemblage(
            company=self.company, kit=SimpleNamespace(id=4501),
            composants=[SimpleNamespace(
                produit=self.cable, quantite=quantite_par_kit)],
            produit_compose=self.composite,
            quantite_produite=quantite_produite,
            reference='OA-ASTK45', user=self.user)

    def test_assemblage_decimal_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            with transaction.atomic():
                self._assembler(Decimal('0.5'), 3)
        message = str(ctx.exception.detail['quantite'][0])
        self.assertIn('1,5', message)
        self.assertIn('Câble 6 mm²', message)
        self.assertIn('unité de stock entière exigée', message)
        self.cable.refresh_from_db()
        self.composite.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 10)
        self.assertEqual(self.composite.quantite_stock, 0)
        self.assertFalse(MouvementStock.objects.filter(
            company=self.company).exists())

    def test_assemblage_decimal_entier_accepte(self):
        # 0,5 × 4 = 2 : entier, accepté — stock 10 → 8, mouvement de 2.
        self._assembler(Decimal('0.5'), 4)
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 8)
        mvt = MouvementStock.objects.get(produit=self.cable)
        self.assertEqual(mvt.quantite, 2)
        self.assertEqual(mvt.quantite_apres - mvt.quantite_avant, -2)

    def test_record_stock_movement_refuse_decimal(self):
        for valeur in (Decimal('1.5'), 2.25):
            with self.assertRaises(ValidationError):
                with transaction.atomic():
                    record_stock_movement(
                        company=self.company, produit=self.cable,
                        type_mouvement=mouvement_type_sortie(),
                        quantite=valeur, quantite_avant=10,
                        quantite_apres=8, reference='T-ASTK45', note='',
                        created_by=self.user)
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 10)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.cable).exists())

    def test_record_stock_movement_accepte_decimal_entier(self):
        mvt = record_stock_movement(
            company=self.company, produit=self.cable,
            type_mouvement=mouvement_type_sortie(),
            quantite=Decimal('2.000'), quantite_avant=10, quantite_apres=8,
            reference='T-ASTK45', note='', created_by=self.user)
        mvt.refresh_from_db()
        self.assertEqual(mvt.quantite, 2)
