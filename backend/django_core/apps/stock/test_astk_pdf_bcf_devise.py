"""ASTK64 — le PDF du BCF est imprimé dans la devise du document, avec la
contre-valeur MAD en mention.

Constat C-ASTK-015 (sonde BCF-9) : un BCF EUR (taux 10,8, ligne 100 EUR =
1 080 MAD) imprimait « 1080.00 MAD » — ni « EUR » ni « 100.00 » : le
fournisseur recevait des montants qui n'étaient pas ceux convenus.

Le test porte sur le HTML rendu par le contexte et le gabarit réels (pas de
mock ; WeasyPrint n'est pas nécessaire pour lire les montants).

Run :
    python manage.py test apps.stock.test_astk_pdf_bcf_devise -v 2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.stock.utils.pdf_fournisseur import build_bcf_context
from apps.ventes.utils.pdf import _render_html
from authentication.models import Company

_seq = itertools.count(1)


class PdfBcfDeviseTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk64-co-{n}', nom=f'ASTK64 Co {n}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK64')
        self.produit = Produit.objects.create(
            company=self.company, nom='Module ASTK64', sku=f'ASTK64-{n}',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1080'))

    def _html(self, bc):
        return _render_html(
            'bon_commande_fournisseur.html', build_bcf_context(bc))

    def test_bcf_eur_imprime_en_eur_avec_contre_valeur(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK64-{next(_seq)}',
            fournisseur=self.fournisseur, devise='EUR',
            taux_change=Decimal('10.8'))
        bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1080'),
            prix_achat_unitaire_devise=Decimal('100'))
        html = self._html(bc)
        self.assertIn('100.00 EUR', html)
        self.assertNotIn('1080.00 MAD', html)
        self.assertIn('contre-valeur : 1 080.00 MAD (taux 10,8)', html)

    def test_bcf_mad_inchange(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK64-{next(_seq)}',
            fournisseur=self.fournisseur)
        bc.lignes.create(
            produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal('1080'))
        html = self._html(bc)
        self.assertIn('1080.00 MAD', html)
        self.assertIn('2160.00 MAD', html)
        self.assertNotIn('contre-valeur', html)
        self.assertNotIn('.00 EUR', html)
