"""ASTK65 — la TVA du PDF BCF (et de l'avoir préparé depuis un retour) est
ventilée par ligne au taux du produit, avec le même helper que la facture
fournisseur : le TTC du BCF envoyé = le TTC de la facture qui en naît.

Constat C-ASTK-015 (sonde BCF-8) : produit à 10 %, BCF 1 × 1 000 HT — le PDF
imprimait TVA 200,00 / TTC 1 200,00 (20 % fixe) alors que la facture née de
la réception portait TVA 100,00 / TTC 1 100,00.

Run :
    python manage.py test apps.stock.test_astk_pdf_bcf_tva -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
    RetourFournisseur,
)
from apps.stock.services import (
    apply_retour_fournisseur, confirm_reception_fournisseur,
    facturer_reception, preparer_avoir_depuis_retour, ventiler_tva_achats,
)
from apps.stock.utils.pdf_fournisseur import build_bcf_context
from apps.ventes.utils.pdf import _render_html
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class PdfBcfTvaTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk65-co-{n}', nom=f'ASTK65 Co {n}')
        self.user = User.objects.create_user(
            username=f'astk65-{n}', password='x', company=self.company,
            role_legacy='admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK65')
        self.produit = Produit.objects.create(
            company=self.company, nom='Pompe ASTK65', sku=f'ASTK65-{n}',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'),
            tva=Decimal('10'), quantite_stock=0)
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK65-{n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = self.bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'))

    def test_pdf_egal_facture(self):
        context = build_bcf_context(self.bc)
        self.assertEqual(context['total_tva_standard'], Decimal('100.00'))
        self.assertEqual(context['total_ttc_standard'], Decimal('1100.00'))
        html = _render_html('bon_commande_fournisseur.html', context)
        self.assertIn('1100.00 MAD', html)
        self.assertNotIn('1200.00 MAD', html)

        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK65-{next(_seq)}',
            bon_commande=self.bc, created_by=self.user)
        rec.lignes.create(ligne_commande=self.ligne, produit=self.produit,
                          quantite=1)
        confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        facture = facturer_reception(self.company, self.user, rec)
        self.assertEqual(facture.montant_tva, Decimal('100.00'))
        self.assertEqual(facture.montant_ttc, Decimal('1100.00'))
        self.assertEqual(facture.montant_ttc, context['total_ttc_standard'])

    def test_taux_mixtes_ventiles(self):
        autre = Produit.objects.create(
            company=self.company, nom='Câble ASTK65', sku=f'ASTK65-C-{next(_seq)}',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'))  # sans taux
        self.bc.lignes.create(
            produit=autre, quantite=10, prix_achat_unitaire=Decimal('50'))
        context = build_bcf_context(self.bc)
        self.assertEqual(context['total_tva_standard'], Decimal('200.00'))
        self.assertEqual(
            [(t, tva) for t, _ht, tva in context['tva_par_taux']],
            [(Decimal('10'), Decimal('100.00')),
             (Decimal('20'), Decimal('100.00'))])
        self.assertIsNone(context['taux_tva_standard'])

    def test_avoir_retour_au_taux_du_produit(self):
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=5)
        retour = RetourFournisseur.objects.create(
            company=self.company, reference=f'RET-ASTK65-{next(_seq)}',
            fournisseur=self.fournisseur, bon_commande=self.bc)
        retour.lignes.create(produit=self.produit, quantite=1)
        apply_retour_fournisseur(retour, self.user)
        montants = preparer_avoir_depuis_retour(retour)
        self.assertEqual(montants['montant_tva'], Decimal('100.00'))
        self.assertEqual(montants['montant_ttc'], Decimal('1100.00'))

    def test_helper_unique(self):
        v = ventiler_tva_achats([(Decimal('1000'), self.produit),
                                 (Decimal('100'), None)])
        self.assertEqual(v['total_tva'], Decimal('120.00'))
        self.assertEqual(v['total_ttc'], Decimal('1220.00'))
