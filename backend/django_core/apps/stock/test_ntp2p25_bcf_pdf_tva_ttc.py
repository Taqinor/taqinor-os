"""
NTP2P25 — Bon de commande fournisseur imprimable PDF : chaîne HT/TVA/TTC.

L'action ``bon-commande-fournisseur/{id}/pdf/`` et son gabarit (en-tête
société, lignes, incoterm, conditions de paiement) étaient déjà construits
(QD2/ZPUR8) — le seul gap réel face au critère d'acceptation (« le total
HT/TVA/TTC ») était l'absence de ventilation TVA/TTC (le document
n'affichait que le Total HT). ``LigneBonCommandeFournisseur`` ne porte pas
encore de ``taux_tva`` par ligne (contrairement à XPUR17 côté facture
fournisseur) : le contexte de rendu calcule donc la TVA à un taux STANDARD
(20 %, clairement labellisé), jamais utilisé ailleurs dans l'OS.

Run :
    python manage.py test apps.stock.test_ntp2p25_bcf_pdf_tva_ttc -v2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.stock.utils.pdf_fournisseur import (
    TAUX_TVA_STANDARD_BCF, build_bcf_context,
)


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class ContexteTvaTtcTests(TestCase):
    def setUp(self):
        self.company = _company('ntp2p25-co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P25')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTP2P25', sku='OND-NTP2P25',
            prix_vente=Decimal('5000'), prix_achat=Decimal('3000'))

    def test_total_tva_et_ttc_calcules_au_taux_standard(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTP2P25-1',
            fournisseur=self.fournisseur)
        bc.lignes.create(
            produit=self.produit, quantite=2, prix_achat_unitaire=Decimal('3000'))

        context = build_bcf_context(bc)

        self.assertEqual(context['total_achat'], Decimal('6000'))
        self.assertEqual(context['taux_tva_standard'], TAUX_TVA_STANDARD_BCF)
        self.assertEqual(context['total_tva_standard'], Decimal('1200.00'))
        self.assertEqual(context['total_ttc_standard'], Decimal('7200.00'))

    def test_bcf_sans_ligne_omet_la_ventilation(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTP2P25-2',
            fournisseur=self.fournisseur)

        context = build_bcf_context(bc)

        self.assertEqual(context['total_achat'], Decimal('0'))
        self.assertIsNone(context['taux_tva_standard'])
        self.assertIsNone(context['total_tva_standard'])
        self.assertIsNone(context['total_ttc_standard'])
