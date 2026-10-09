"""ERR-ASTK54-ANNULATION-RECEPTION-FACTUREE — annuler une réception
confirmée ET facturée est refusé (400) tant que la facture issue de la
réception n'est pas supprimée ou neutralisée par un avoir : sinon le stock
repart, la facture reste due et la re-réception se refacture.

Run:
    python manage.py test apps.stock.test_astk54_annulation_reception_facturee
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.stock.models import (
    AvoirFournisseur, BonCommandeFournisseur, FactureFournisseur,
    Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    confirm_reception_fournisseur, facturer_reception,
    imputer_avoir_fournisseur,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class AnnulationReceptionFactureeTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'errastk54-co-{n}', nom=f'ERR ASTK54 Co {n}')
        role = Role.objects.create(
            company=self.company, nom=f'r-errastk54-{n}',
            permissions=['roles_gerer', 'stock_voir', 'stock_modifier',
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username=f'errastk54-{n}', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ERR-ASTK54')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ERR-ASTK54',
            sku=f'ERRASTK54-{n}', prix_achat=Decimal('100'),
            prix_vente=Decimal('150'), quantite_stock=0)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ERRASTK54-{n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = self.bcf.lignes.create(
            produit=self.produit, quantite=4,
            prix_achat_unitaire=Decimal('100'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ERRASTK54-{n}',
            bon_commande=self.bcf)
        self.reception.lignes.create(
            ligne_commande=ligne_cmd, produit=self.produit, quantite=4)
        confirm_reception_fournisseur(self.reception, self.user)
        self.reception.refresh_from_db()
        self.facture = facturer_reception(
            self.company, self.user, self.reception)

    def _annuler(self):
        return self.api.post(
            '/api/django/stock/receptions-fournisseur/'
            f'{self.reception.id}/annuler/', {}, format='json')

    def test_facture_liee_par_fk(self):
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.reception_id, self.reception.id)

    def test_reception_facturee_annulation_refusee(self):
        self.produit.refresh_from_db()
        stock_avant = self.produit.quantite_stock
        self.assertEqual(stock_avant, 4)
        solde_avant = FactureFournisseur.objects.get(
            pk=self.facture.pk).solde_du
        resp = self._annuler()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn(self.facture.reference, str(resp.data['detail']))
        # Rien n'a bougé : réception, stock, facture.
        self.reception.refresh_from_db()
        self.assertEqual(
            self.reception.statut, ReceptionFournisseur.Statut.CONFIRME)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, stock_avant)
        self.assertEqual(
            FactureFournisseur.objects.get(pk=self.facture.pk).solde_du,
            solde_avant)

    def test_facture_supprimee_annulation_acceptee(self):
        resp = self.api.delete(
            f'/api/django/stock/factures-fournisseur/{self.facture.id}/')
        self.assertIn(resp.status_code, (200, 204), resp.data)
        resp = self._annuler()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.reception.refresh_from_db()
        self.assertEqual(
            self.reception.statut, ReceptionFournisseur.Statut.ANNULE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)

    def test_facture_neutralisee_par_avoir_annulation_acceptee(self):
        ttc = self.facture.montant_ttc
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ERRASTK54',
            fournisseur=self.fournisseur, montant_ttc=ttc,
            statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, self.facture, ttc, user=self.user)
        resp = self._annuler()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.reception.refresh_from_db()
        self.assertEqual(
            self.reception.statut, ReceptionFournisseur.Statut.ANNULE)

    def test_reference_prefixe_ne_bloque_pas(self):
        """Une facture d'une AUTRE réception dont la référence commence
        pareil (REC-…-1 vs REC-…-10) ne bloque pas l'annulation (repli sur
        la note, factures antérieures à la FK)."""
        FactureFournisseur.objects.filter(pk=self.facture.pk).update(
            reception=None,
            note=f'Facture réception {self.reception.reference}0')
        resp = self._annuler()
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_facture_historique_sans_fk_bloque_par_note(self):
        FactureFournisseur.objects.filter(pk=self.facture.pk).update(
            reception=None)
        resp = self._annuler()
        self.assertEqual(resp.status_code, 400, resp.data)
