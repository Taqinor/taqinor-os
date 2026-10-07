"""ASTK102/ASTK103 — le statut de règlement d'une facture fournisseur est une
projection de `solde_du` (paiements + acomptes + avoirs imputés), recalculée
après chaque imputation ; le portail fournisseur somme les SOLDES.

Run:
    python manage.py test apps.stock.test_astk_statut_solde_fournisseur
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
    AcompteFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    FactureFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import facturer_reception, imputer_avoir_fournisseur

User = get_user_model()


class _Base(TestCase):
    slug = 'astk102'

    def setUp(self):
        self.company = Company.objects.create(
            nom=f'{self.slug}-co', slug=f'{self.slug}-co')
        role = Role.objects.create(
            company=self.company, nom=f'r-{self.slug}',
            permissions=['stock_voir', 'stock_modifier', 'prix_achat_voir'])
        self.user = User.objects.create_user(
            username=f'{self.slug}-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur {self.slug}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'OND-{self.slug}',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            tva=Decimal('20'))
        self.n = 0

    def _bcf_recu(self, quantite=10, pu=Decimal('1000')):
        """BCF reçu en entier (réception CONFIRMÉE), HT = quantite × pu."""
        self.n += 1
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{self.slug}-{self.n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=pu)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-{self.slug}-{self.n}',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=quantite)
        return bcf, rec

    def _facture_simple(self, ttc):
        self.n += 1
        return FactureFournisseur.objects.create(
            company=self.company, reference=f'FF-{self.slug}-{self.n}',
            fournisseur=self.fournisseur,
            montant_ht=(ttc / Decimal('1.2')).quantize(Decimal('0.01')),
            montant_tva=ttc - (ttc / Decimal('1.2')).quantize(
                Decimal('0.01')),
            montant_ttc=ttc)


class StatutSoldeTests(_Base):
    slug = 'astk102'

    def test_acompte_plus_paiement_payee(self):
        bcf, rec = self._bcf_recu()
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('3600'))
        facture = facturer_reception(self.company, self.user, rec)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.montant_ttc, Decimal('12000.00'))
        self.assertEqual(facture.solde_du, Decimal('8400.00'))
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/paiements/',
            {'montant': '8400', 'date_paiement': '2026-10-02'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.solde_du, Decimal('0.00'))
        self.assertEqual(facture.statut, FactureFournisseur.Statut.PAYEE)

    def test_avoir_total_payee(self):
        facture = self._facture_simple(Decimal('12000'))
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ASTK102-1',
            fournisseur=self.fournisseur, montant_ttc=Decimal('12000'),
            statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, facture, user=self.user)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.solde_du, Decimal('0.00'))
        self.assertEqual(facture.statut, FactureFournisseur.Statut.PAYEE)

    def test_avoir_partiel_partiellement_payee(self):
        facture = self._facture_simple(Decimal('12000'))
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ASTK102-2',
            fournisseur=self.fournisseur, montant_ttc=Decimal('2000'),
            statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, facture, user=self.user)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(
            facture.statut, FactureFournisseur.Statut.PARTIELLEMENT_PAYEE)

    def test_comptes_a_payer_exclut_solde_zero(self):
        soldee = self._facture_simple(Decimal('12000'))
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ASTK102-3',
            fournisseur=self.fournisseur, montant_ttc=Decimal('12000'),
            statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, soldee, user=self.user)
        bcf, rec = self._bcf_recu()
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('3600'))
        par_acompte = facturer_reception(self.company, self.user, rec)
        self.api.post(
            f'/api/django/stock/factures-fournisseur/{par_acompte.id}/'
            'paiements/',
            {'montant': '8400', 'date_paiement': '2026-10-02'},
            format='json')
        intacte = self._facture_simple(Decimal('600'))
        resp = self.api.get(
            '/api/django/stock/factures-fournisseur/comptes-a-payer/')
        self.assertEqual(resp.status_code, 200)
        ids = {f['id'] for f in resp.data['results']}
        self.assertNotIn(soldee.id, ids)
        self.assertNotIn(par_acompte.id, ids)
        self.assertIn(intacte.id, ids)
        self.assertEqual(Decimal(resp.data['total_du']), Decimal('600.00'))
        intacte = FactureFournisseur.objects.get(pk=intacte.pk)
        self.assertEqual(intacte.statut, FactureFournisseur.Statut.A_PAYER)


class PortailMontantTests(_Base):
    """ASTK103 — accueil du portail fournisseur = somme des soldes."""
    slug = 'astk103'

    def test_montant_a_payer_egal_somme_soldes(self):
        from apps.stock.selectors import resume_portail_fournisseur
        # Facture TTC 10 000 réglée 9 000 (paiement réel via l'API).
        reglee = self._facture_simple(Decimal('10000'))
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{reglee.id}/paiements/',
            {'montant': '9000', 'date_paiement': '2026-10-02'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Facture soldée par acompte (acompte = TTC 1 200).
        bcf, rec = self._bcf_recu(quantite=1, pu=Decimal('1000'))
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('1200'))
        par_acompte = facturer_reception(self.company, self.user, rec)
        par_acompte = FactureFournisseur.objects.get(pk=par_acompte.pk)
        self.assertEqual(par_acompte.solde_du, Decimal('0.00'))

        resume = resume_portail_fournisseur(
            self.company, self.fournisseur.id)
        self.assertEqual(resume['montant_a_payer'], '1000.00')
        self.assertEqual(resume['factures_a_payer'], 1)
        # Égal au total des soldes des factures de ce fournisseur.
        total_soldes = sum(
            (f.solde_du for f in FactureFournisseur.objects.filter(
                company=self.company, fournisseur=self.fournisseur)),
            Decimal('0'))
        self.assertEqual(Decimal(resume['montant_a_payer']), total_soldes)
