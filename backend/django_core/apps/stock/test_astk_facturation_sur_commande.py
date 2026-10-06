"""ASTK108/ASTK109 — facturation fournisseur « sur commande » (ZPUR1) vs
« sur réception » (FG56) : une ligne sur commande n'est jamais facturée deux
fois ; les deux chemins partagent un constructeur unique (date, acomptes,
événement).

Run:
    python manage.py test apps.stock.test_astk_facturation_sur_commande
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import facturer_bcf_sur_commande, facturer_reception

User = get_user_model()


class _Base(TestCase):
    slug = 'astk108'

    def setUp(self):
        self.company = Company.objects.create(
            nom=f'{self.slug}-co', slug=f'{self.slug}-co')
        role = Role.objects.create(
            company=self.company, nom=f'r-{self.slug}',
            permissions=['stock_voir', 'stock_modifier'])
        self.user = User.objects.create_user(
            username=f'{self.slug}-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur {self.slug}')
        self.p_commande = Produit.objects.create(
            company=self.company, nom='Panneau import',
            sku=f'PV-CMD-{self.slug}', prix_vente=Decimal('200'),
            prix_achat=Decimal('100'), tva=Decimal('20'),
            politique_facturation_achat=(
                Produit.PolitiqueFacturationAchat.SUR_COMMANDE))
        self.p_reception = Produit.objects.create(
            company=self.company, nom='Câble', sku=f'CAB-REC-{self.slug}',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            tva=Decimal('20'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{self.slug}-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.l_commande = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.p_commande, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        self.n = 0

    def _reception(self, lignes):
        self.n += 1
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-{self.slug}-{self.n}',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        for ligne_bcf, quantite in lignes:
            LigneReceptionFournisseur.objects.create(
                reception=rec, ligne_commande=ligne_bcf,
                produit=ligne_bcf.produit, quantite=quantite)
        return rec

    def _total_ht_bcf(self):
        return FactureFournisseur.objects.filter(
            company=self.company, bon_commande=self.bcf).aggregate(
            t=Sum('montant_ht'))['t']


class SurCommandeTests(_Base):
    slug = 'astk108'

    def test_ligne_sur_commande_pas_refacturee(self):
        facturer_bcf_sur_commande(self.company, self.user, self.bcf)
        rec = self._reception([(self.l_commande, 10)])
        with self.assertRaisesMessage(ValueError, 'Rien à facturer'):
            facturer_reception(self.company, self.user, rec)
        # Relu : une seule facture, Σ HT = 1 000.
        self.assertEqual(
            FactureFournisseur.objects.filter(
                company=self.company, bon_commande=self.bcf).count(), 1)
        self.assertEqual(self._total_ht_bcf(), Decimal('1000.00'))

    def test_reception_mixte_ne_facture_que_sur_reception(self):
        l_reception = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.p_reception, quantite=50,
            prix_achat_unitaire=Decimal('10'))
        facturer_bcf_sur_commande(self.company, self.user, self.bcf)
        rec = self._reception([(self.l_commande, 10), (l_reception, 50)])
        facture = facturer_reception(self.company, self.user, rec)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.montant_ht, Decimal('500.00'))
        self.assertEqual(
            list(facture.lignes.values_list('designation', flat=True)),
            ['Câble'])
        self.assertEqual(self._total_ht_bcf(), Decimal('1500.00'))
