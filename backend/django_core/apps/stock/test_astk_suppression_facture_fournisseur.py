"""ASTK85 — suppression d'une facture fournisseur portant un acompte ou un
avoir imputé, et d'un avoir portant une imputation : refusée (400) comme
pour les paiements — plus aucun crédit fournisseur évaporé (C-ASTK-018).

Run:
    python manage.py test apps.stock.test_astk_suppression_facture_fournisseur
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AcompteFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    FactureFournisseur, Fournisseur,
)
from apps.stock.services import imputer_avoir_fournisseur

User = get_user_model()


class SuppressionFactureFournisseurTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk85-co', slug='astk85-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk85-admin',
            permissions=['roles_gerer', 'stock_voir', 'stock_modifier'])
        self.user = User.objects.create_user(
            username='astk85-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK85')
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK85-0001',
            fournisseur=self.fournisseur)

    def _facture(self, ref, bcf=None):
        return FactureFournisseur.objects.create(
            company=self.company, reference=ref,
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))

    def _avoir_impute(self, facture, montant=Decimal('500')):
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ASTK85-0001',
            fournisseur=self.fournisseur, montant_ttc=montant,
            statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, facture, montant, user=self.user)
        avoir.refresh_from_db()
        return avoir

    def test_facture_avec_avoir_impute_refusee(self):
        f = self._facture('FF-ASTK85-F')
        avoir = self._avoir_impute(f)
        solde_avant = FactureFournisseur.objects.get(pk=f.pk).solde_du
        resp = self.api.delete(
            f'/api/django/stock/factures-fournisseur/{f.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('avoir', str(resp.data['detail']).lower())
        # Persistance : facture et avoir relus — identiques.
        self.assertTrue(FactureFournisseur.objects.filter(pk=f.pk).exists())
        self.assertEqual(
            FactureFournisseur.objects.get(pk=f.pk).solde_du, solde_avant)
        avoir.refresh_from_db()
        self.assertEqual(avoir.montant_impute, Decimal('500.00'))
        self.assertEqual(avoir.imputations.count(), 1)
        self.assertEqual(
            self.api.get(
                f'/api/django/stock/factures-fournisseur/{f.id}/'
            ).status_code, 200)

    def test_facture_avec_acompte_impute_refusee(self):
        g = self._facture('FF-ASTK85-G', bcf=self.bcf)
        acompte = AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('300'))
        from apps.stock.services import imputer_acomptes_bcf
        imputer_acomptes_bcf(self.bcf)
        acompte.refresh_from_db()
        self.assertEqual(acompte.facture_imputee_id, g.id)
        resp = self.api.delete(
            f'/api/django/stock/factures-fournisseur/{g.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('acompte', str(resp.data['detail']).lower())
        self.assertTrue(FactureFournisseur.objects.filter(pk=g.pk).exists())
        acompte.refresh_from_db()
        self.assertEqual(acompte.facture_imputee_id, g.id)
        self.assertEqual(acompte.montant_consomme, Decimal('300.00'))

    def test_avoir_impute_non_supprimable(self):
        f = self._facture('FF-ASTK85-H')
        avoir = self._avoir_impute(f)
        resp = self.api.delete(
            f'/api/django/stock/avoirs-fournisseur/{avoir.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('imput', str(resp.data['detail']).lower())
        self.assertTrue(AvoirFournisseur.objects.filter(pk=avoir.pk).exists())
        avoir.refresh_from_db()
        self.assertEqual(avoir.montant_impute, Decimal('500.00'))
        self.assertEqual(
            self.api.get(
                f'/api/django/stock/avoirs-fournisseur/{avoir.id}/'
            ).status_code, 200)

    def test_avoir_sans_imputation_supprimable(self):
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ASTK85-0009',
            fournisseur=self.fournisseur, montant_ttc=Decimal('100'))
        resp = self.api.delete(
            f'/api/django/stock/avoirs-fournisseur/{avoir.id}/')
        self.assertEqual(resp.status_code, 204)

    def test_facture_nue_supprimable(self):
        f = self._facture('FF-ASTK85-N')
        resp = self.api.delete(
            f'/api/django/stock/factures-fournisseur/{f.id}/')
        self.assertEqual(resp.status_code, 204)
