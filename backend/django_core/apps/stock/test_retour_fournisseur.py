"""Tests retour fournisseur (N19) — couche service.

Couvre :
  - validation d'un retour → décrément de stock (MouvementStock SORTIE) ;
  - idempotence : un retour déjà validé ne re-décrémente pas ;
  - retour vide refusé ;
  - lien optionnel vers le bon de commande d'origine.

Usage INTERNE (prix d'achat jamais client-facing).

Run :
    python manage.py test apps.stock.test_retour_fournisseur -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    Produit, Fournisseur, MouvementStock, BonCommandeFournisseur,
    RetourFournisseur, LigneRetourFournisseur,
)
from apps.stock.services import apply_retour_fournisseur

User = get_user_model()


def make_company(slug='ret-co', nom='Ret Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class RetourBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ret_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste')
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble 6mm', sku='CAB6',
            prix_achat=Decimal('10'), prix_vente=Decimal('15'),
            quantite_stock=50)

    def _retour(self, qte=5, bon=None):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-209901-0001',
            fournisseur=self.fournisseur, bon_commande=bon)
        LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.produit, quantite=qte,
            motif='défectueux')
        return retour


class TestRetour(RetourBase):
    def test_validation_decreases_stock(self):
        retour = self._retour(qte=5)
        apply_retour_fournisseur(retour, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 45)
        self.assertEqual(retour.statut, RetourFournisseur.Statut.VALIDE)
        mv = MouvementStock.objects.get(
            produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mv.quantite, 5)
        self.assertEqual(mv.quantite_apres, 45)

    def test_double_validation_idempotent(self):
        retour = self._retour(qte=5)
        apply_retour_fournisseur(retour, self.user)
        with self.assertRaises(ValueError):
            apply_retour_fournisseur(retour, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 45)  # pas re-décrémenté

    def test_empty_retour_refused(self):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-209901-0002',
            fournisseur=self.fournisseur)
        with self.assertRaises(ValueError):
            apply_retour_fournisseur(retour, self.user)

    def test_links_to_bon_commande(self):
        bon = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-209901-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        retour = self._retour(qte=3, bon=bon)
        apply_retour_fournisseur(retour, self.user)
        retour.refresh_from_db()
        self.assertEqual(retour.bon_commande_id, bon.id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 47)
