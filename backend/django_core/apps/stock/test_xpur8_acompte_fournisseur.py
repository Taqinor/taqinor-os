"""XPUR8 — Acomptes / avances fournisseur sur BCF.

Couvre :
  * un acompte de 30 % sur un BCF réduit le solde dû de la facture finale ;
  * un acompte ne s'impute qu'une fois (idempotent) ;
  * visible dans le selector trésorerie (acomptes_fournisseur_ouverts) ;
  * multi-tenant.

Run:
    python manage.py test apps.stock.test_xpur8_acompte_fournisseur -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AcompteFournisseur, BonCommandeFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, Produit,
    ReceptionFournisseur, LigneReceptionFournisseur,
)
from apps.stock.selectors import acomptes_fournisseur_ouverts
from apps.stock.services import facturer_reception, imputer_acomptes_bcf

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


class Xpur8Base(TestCase):
    def setUp(self):
        self.company = _company('xpur8-co')
        self.user = _user(
            self.company, 'xpur8-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Import Fournisseur')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur import', sku='OND-XPUR8',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR8-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))


class TestAcompteCreation(Xpur8Base):
    def test_create_acompte_via_endpoint(self):
        resp = self.api.post('/api/django/stock/acomptes-fournisseur/', {
            'bon_commande': self.bcf.id, 'montant': '3000',
            'date_versement': '2026-06-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant']), Decimal('3000.00'))
        self.assertEqual(
            Decimal(resp.data['montant_non_consomme']), Decimal('3000.00'))

    def test_visible_on_bcf_detail(self):
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('3000'), date_versement=datetime.date(2026, 6, 1))
        resp = self.api.get(
            f'/api/django/stock/bons-commande-fournisseur/{self.bcf.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['acomptes']), 1)


class TestImputationOnFacture(Xpur8Base):
    def _confirm_reception(self):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-XPUR8-0001',
            bon_commande=self.bcf, statut=ReceptionFournisseur.Statut.BROUILLON,
            date_reception=datetime.date(2026, 6, 15))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=self.ligne, produit=self.produit,
            quantite=10)
        rec.statut = ReceptionFournisseur.Statut.CONFIRME
        rec.save(update_fields=['statut'])
        return rec

    def test_30pct_acompte_reduces_solde_du(self):
        # 10 000 HT (10 x 1000) -> TTC via facturer_reception (TVA 20% =
        # 12 000 TTC). 30% acompte = 3 600.
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('3600'), date_versement=datetime.date(2026, 6, 1))
        rec = self._confirm_reception()
        facture = facturer_reception(self.company, self.user, rec)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_ttc, Decimal('12000.00'))
        self.assertEqual(facture.total_acomptes_imputes, Decimal('3600.00'))
        self.assertEqual(facture.solde_du, Decimal('8400.00'))

    def test_imputation_idempotent(self):
        acompte = AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('3600'), date_versement=datetime.date(2026, 6, 1))
        rec = self._confirm_reception()
        facture = facturer_reception(self.company, self.user, rec)
        # Re-run imputation manually — must not double-impute or change the
        # already-set facture_imputee.
        imputer_acomptes_bcf(self.bcf)
        acompte.refresh_from_db()
        self.assertEqual(acompte.facture_imputee_id, facture.id)
        self.assertEqual(acompte.montant_consomme, Decimal('3600.00'))
        facture.refresh_from_db()
        self.assertEqual(facture.total_acomptes_imputes, Decimal('3600.00'))

    def test_solde_du_never_negative(self):
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('99999'), date_versement=datetime.date(2026, 6, 1))
        rec = self._confirm_reception()
        facture = facturer_reception(self.company, self.user, rec)
        facture.refresh_from_db()
        self.assertGreaterEqual(facture.solde_du, Decimal('0'))

    def test_no_acompte_unchanged_behaviour(self):
        rec = self._confirm_reception()
        facture = facturer_reception(self.company, self.user, rec)
        facture.refresh_from_db()
        self.assertEqual(facture.total_acomptes_imputes, Decimal('0'))
        self.assertEqual(facture.solde_du, facture.montant_ttc)


class TestTresorerieSelector(Xpur8Base):
    def test_open_acompte_listed(self):
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('3600'), date_versement=datetime.date(2026, 6, 1))
        rows = acomptes_fournisseur_ouverts(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['montant_non_consomme'], Decimal('3600'))

    def test_fully_consumed_acompte_not_listed(self):
        a = AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('3600'), montant_consomme=Decimal('3600'),
            date_versement=datetime.date(2026, 6, 1))
        rows = acomptes_fournisseur_ouverts(self.company)
        self.assertEqual(len(rows), 0)
        self.assertIsNotNone(a)


class TestMultiTenant(Xpur8Base):
    def test_cross_company_bcf_rejected(self):
        other_company = _company('xpur8-co-2')
        other_bcf = BonCommandeFournisseur.objects.create(
            company=other_company, reference='BCF-OTHER-0001',
            fournisseur=Fournisseur.objects.create(
                company=other_company, nom='Autre'))
        resp = self.api.post('/api/django/stock/acomptes-fournisseur/', {
            'bon_commande': other_bcf.id, 'montant': '1000',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
