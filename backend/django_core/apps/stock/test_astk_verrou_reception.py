"""ASTK49 — double confirmation / double annulation d'une réception
fournisseur (et double validation d'un retour) : un seul effet.

Constat C-ASTK-010 (sondes BCF-6 et MVT-9) : ``confirm_reception_fournisseur``
et ``annuler_reception_confirmee`` testaient le statut sur l'instance PASSÉE.
Une 2e confirmation sur un objet périmé était acceptée (2 ENTREE, stock 8,
quantite_recue 8) ; une 2e annulation contre-passait encore (40→30→20).
Les instances périmées sont la simulation déterministe de la course.

Run :
    python manage.py test apps.stock.test_astk_verrou_reception -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, MouvementStock, Produit,
    ReceptionFournisseur, RetourFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, apply_retour_fournisseur,
    confirm_reception_fournisseur,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class VerrouReceptionTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            slug=f'astk49-co-{n}', nom=f'ASTK49 Co {n}')
        self.user = User.objects.create_user(
            username=f'astk49-{n}', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK49')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK49', sku=f'ASTK49-{n}',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=0)

    def _bcf(self, quantite=10):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK49-{next(_seq)}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('100'))
        return bc, ligne_cmd

    def _reception(self, bc, ligne_cmd, quantite):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK49-{next(_seq)}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(
            ligne_commande=ligne_cmd, produit=self.produit, quantite=quantite)
        return rec

    def test_double_confirmation(self):
        bc, ligne_cmd = self._bcf(10)
        rec = self._reception(bc, ligne_cmd, 4)
        a = ReceptionFournisseur.objects.get(pk=rec.pk)
        b = ReceptionFournisseur.objects.get(pk=rec.pk)  # instance périmée

        confirm_reception_fournisseur(a, self.user)
        with self.assertRaisesMessage(ValueError, 'déjà confirmée'):
            confirm_reception_fournisseur(b, self.user)

        self.produit.refresh_from_db()
        ligne_cmd.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 4)
        self.assertEqual(ligne_cmd.quantite_recue, 4)
        self.assertEqual(MouvementStock.objects.filter(
            produit=self.produit, reference=rec.reference,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE).count(), 1)

    def test_double_annulation(self):
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=30)
        bc, ligne_cmd = self._bcf(10)
        rec = self._reception(bc, ligne_cmd, 10)
        confirm_reception_fournisseur(rec, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 40)
        a = ReceptionFournisseur.objects.get(pk=rec.pk)
        b = ReceptionFournisseur.objects.get(pk=rec.pk)  # instance périmée

        annuler_reception_confirmee(a, self.user)
        with self.assertRaisesMessage(ValueError, 'déjà annulée'):
            annuler_reception_confirmee(b, self.user)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 30)
        self.assertEqual(MouvementStock.objects.filter(
            produit=self.produit,
            reference=f'ANNUL-{rec.reference}').count(), 1)
        ligne_cmd.refresh_from_db()
        self.assertEqual(ligne_cmd.quantite_recue, 0)

    def test_double_validation_retour(self):
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=10)
        retour = RetourFournisseur.objects.create(
            company=self.company, reference=f'RET-ASTK49-{self.n}',
            fournisseur=self.fournisseur)
        retour.lignes.create(produit=self.produit, quantite=3)
        a = RetourFournisseur.objects.get(pk=retour.pk)
        b = RetourFournisseur.objects.get(pk=retour.pk)  # instance périmée

        apply_retour_fournisseur(a, self.user)
        with self.assertRaisesMessage(ValueError, 'brouillon'):
            apply_retour_fournisseur(b, self.user)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)
        self.assertEqual(MouvementStock.objects.filter(
            produit=self.produit, reference=retour.reference).count(), 1)
