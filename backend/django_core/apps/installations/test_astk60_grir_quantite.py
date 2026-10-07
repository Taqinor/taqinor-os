"""ASTK60 — la provision GR/IR d'une réception porte sur la quantité
RÉELLEMENT entrée (`quantite_appliquee`, ASTK59), jamais sur la saisie.

Rejoue RESA-11 : BCF ligne 10 @ 60, réception de 12 confirmée → stock +10
mais provision 720,00 (attendu 600,00). Une ligne déjà soldée (entrée à 0)
n'est pas provisionnée. Source réelle : `confirm_reception_fournisseur`
(émet l'événement, l'abonné installations provisionne) — aucun mock.

Run :
    python manage.py test apps.installations.test_astk60_grir_quantite
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations.models_gr_ir import ReceptionNonFacturee
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur

User = get_user_model()


class GrirQuantiteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-astk60', defaults={'nom': 'Co ASTK60'})
        self.user = User.objects.create_user(
            username='resp-astk60', password='x', company=self.company,
            role_legacy='responsable')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK60', sku='SKU-ASTK60-1',
            prix_vente=Decimal('100'), quantite_stock=0)
        self.produit2 = Produit.objects.create(
            company=self.company, nom='Panneau ASTK60', sku='SKU-ASTK60-2',
            prix_vente=Decimal('100'), quantite_stock=0)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ASTK60')
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=fournisseur,
            reference='BCF-ASTK60', statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('60'))
        self.ligne_cmd2 = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.produit2, quantite=5,
            prix_achat_unitaire=Decimal('20'))

    def _reception(self, ref, lignes):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=ref, bon_commande=self.bc)
        for ligne_cmd, produit, qte in lignes:
            LigneReceptionFournisseur.objects.create(
                reception=rec, ligne_commande=ligne_cmd, produit=produit,
                quantite=qte)
        confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        return rec

    def test_sur_reception_provisionne_le_recu(self):
        rec = self._reception(
            'REC-ASTK60-1', [(self.ligne_cmd, self.produit, 12)])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        provision = ReceptionNonFacturee.objects.get(reception=rec)
        self.assertEqual(provision.montant_provision, Decimal('600.00'))

    def test_ligne_soldee_non_provisionnee(self):
        self._reception('REC-ASTK60-A', [(self.ligne_cmd, self.produit, 10)])
        # La ligne onduleur est soldée : sur la 2e réception elle entre à 0,
        # seule la ligne panneau (5 @ 20) entre.
        rec = self._reception('REC-ASTK60-B', [
            (self.ligne_cmd, self.produit, 3),
            (self.ligne_cmd2, self.produit2, 5)])
        provision = ReceptionNonFacturee.objects.get(reception=rec)
        self.assertEqual(provision.montant_provision, Decimal('100.00'))
