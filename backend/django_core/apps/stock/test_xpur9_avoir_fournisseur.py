"""XPUR9 — Avoir fournisseur (note de crédit AP).

Couvre :
  * un retour validé propose un avoir pré-rempli (generer-avoir) ;
  * l'imputation réduit le solde dû (jamais sous zéro) ;
  * la balance FG132 en tient compte (solde_du déduit total_avoirs_imputes) ;
  * multi-tenant + garde-fous (retour non validé, avoir déjà généré,
    fournisseurs différents).

Run:
    python manage.py test apps.stock.test_xpur9_avoir_fournisseur -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AvoirFournisseur, BonCommandeFournisseur, FactureFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, LigneRetourFournisseur,
    Produit, RetourFournisseur,
)
from apps.stock.services import (
    apply_retour_fournisseur, creer_avoir_depuis_retour,
    imputer_avoir_fournisseur, preparer_avoir_depuis_retour,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur9Base(TestCase):
    def setUp(self):
        self.company = _company('xpur9-co')
        self.user = _user(
            self.company, 'xpur9-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Retours')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau défectueux', sku='PV-XPUR9',
            prix_vente=Decimal('1500'), prix_achat=Decimal('900'),
            quantite_stock=20)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR9-0001',
            fournisseur=self.fournisseur)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=20,
            prix_achat_unitaire=Decimal('900'), quantite_recue=20)

    def _retour_valide(self, quantite=5):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-XPUR9-0001',
            fournisseur=self.fournisseur, bon_commande=self.bcf)
        LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.produit, quantite=quantite,
            motif='Défectueux')
        apply_retour_fournisseur(retour, self.user)
        return retour


class TestPreparerAvoir(Xpur9Base):
    def test_montants_derived_from_bcf_price(self):
        retour = self._retour_valide(quantite=5)
        montants = preparer_avoir_depuis_retour(retour)
        # 5 x 900 = 4500 HT, TVA 20% = 900, TTC = 5400.
        self.assertEqual(montants['montant_ht'], Decimal('4500'))
        self.assertEqual(montants['montant_tva'], Decimal('900.00'))
        self.assertEqual(montants['montant_ttc'], Decimal('5400.00'))


class TestGenererAvoirDepuisRetour(Xpur9Base):
    def test_valide_retour_generates_prefilled_avoir(self):
        retour = self._retour_valide(quantite=5)
        avoir = creer_avoir_depuis_retour(self.company, retour, user=self.user)
        self.assertEqual(avoir.statut, AvoirFournisseur.Statut.BROUILLON)
        self.assertEqual(avoir.montant_ttc, Decimal('5400.00'))
        self.assertEqual(avoir.retour_id, retour.id)
        self.assertTrue(avoir.reference.startswith('AVF'))

    def test_non_validated_retour_refused(self):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-XPUR9-0002',
            fournisseur=self.fournisseur)
        with self.assertRaises(ValueError):
            creer_avoir_depuis_retour(self.company, retour, user=self.user)

    def test_double_generation_refused(self):
        retour = self._retour_valide(quantite=5)
        creer_avoir_depuis_retour(self.company, retour, user=self.user)
        with self.assertRaises(ValueError):
            creer_avoir_depuis_retour(self.company, retour, user=self.user)

    def test_endpoint_generer_avoir(self):
        retour = self._retour_valide(quantite=5)
        resp = self.api.post(
            f'/api/django/stock/retours-fournisseur/{retour.id}/generer-avoir/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_ttc'], '5400.00')


class TestImputationAvoir(Xpur9Base):
    def _avoir_valide(self, montant_ttc=Decimal('5400')):
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-XPUR9-0001',
            fournisseur=self.fournisseur,
            montant_ht=montant_ttc / Decimal('1.2'),
            montant_tva=montant_ttc - montant_ttc / Decimal('1.2'),
            montant_ttc=montant_ttc,
            statut=AvoirFournisseur.Statut.VALIDE)
        return avoir

    def test_imputation_reduces_solde_du(self):
        avoir = self._avoir_valide()
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR9-0001',
            fournisseur=self.fournisseur, montant_ht=Decimal('10000'),
            montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'))
        imputer_avoir_fournisseur(avoir, facture, user=self.user)
        facture.refresh_from_db()
        avoir.refresh_from_db()
        self.assertEqual(facture.total_avoirs_imputes, Decimal('5400.00'))
        self.assertEqual(facture.solde_du, Decimal('6600.00'))
        self.assertEqual(avoir.montant_impute, Decimal('5400.00'))
        self.assertEqual(avoir.statut, AvoirFournisseur.Statut.IMPUTE)

    def test_solde_du_never_negative(self):
        avoir = self._avoir_valide(montant_ttc=Decimal('99999'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR9-0002',
            fournisseur=self.fournisseur, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        imputer_avoir_fournisseur(avoir, facture, user=self.user)
        facture.refresh_from_db()
        self.assertEqual(facture.solde_du, Decimal('0'))
        # The avoir keeps its unconsumed remainder for future invoices.
        self.assertGreater(avoir.montant_disponible, Decimal('0'))

    def test_different_fournisseur_refused(self):
        avoir = self._avoir_valide()
        other_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre Fournisseur')
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR9-0003',
            fournisseur=other_fournisseur, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        with self.assertRaises(ValueError):
            imputer_avoir_fournisseur(avoir, facture, user=self.user)

    def test_endpoint_imputer(self):
        avoir = self._avoir_valide()
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR9-0004',
            fournisseur=self.fournisseur, montant_ht=Decimal('10000'),
            montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'))
        resp = self.api.post(
            f'/api/django/stock/avoirs-fournisseur/{avoir.id}/imputer/',
            {'facture': facture.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'impute')


class TestMultiTenant(Xpur9Base):
    def test_cross_company_facture_rejected_by_endpoint(self):
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-XPUR9-0002',
            fournisseur=self.fournisseur, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            statut=AvoirFournisseur.Statut.VALIDE)
        other_company = _company('xpur9-co-2')
        other_fournisseur = Fournisseur.objects.create(
            company=other_company, nom='Autre Société')
        other_facture = FactureFournisseur.objects.create(
            company=other_company, reference='FF-OTHER-0001',
            fournisseur=other_fournisseur, montant_ttc=Decimal('1200'))
        resp = self.api.post(
            f'/api/django/stock/avoirs-fournisseur/{avoir.id}/imputer/',
            {'facture': other_facture.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
