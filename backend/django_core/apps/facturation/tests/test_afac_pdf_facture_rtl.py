"""AFAC57 (C-AFAC-050) — rendu RTL du PDF facture arabe : le bloc des
totaux tient dans la page et les montants restent lisibles (chiffres latins
« 1200.00 », « 700.00 ») ; le rendu français est inchangé.

Rejoue la sonde FDOC-11 (blocs x1 = 598 > 595 pt, montants illisibles,
« Reste à payer » rogné). Rendu WeasyPrint RÉEL ; seul l'upload MinIO est
neutralisé (dict en mémoire). Seule la facture rend l'arabe
(``langue_document`` absent d'avoir.html / note_debit.html).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_pdf_facture_rtl"
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _doc(pdf_bytes):
    import fitz
    return fitz.open(stream=pdf_bytes, filetype='pdf')


def _texte(pdf_bytes):
    doc = _doc(pdf_bytes)
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class PdfFactureRtlTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC57 {n}', slug=f'afac57-{n}')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)
        self.client_ar = Client.objects.create(
            company=self.company, nom='Benali', prenom='Omar',
            email=f'afac57-ar-{n}@example.invalid', langue_document='ar')
        self.client_fr = Client.objects.create(
            company=self.company, nom='Benali', prenom='Omar',
            email=f'afac57-fr-{n}@example.invalid')

    def _facture(self, client):
        from apps.ventes.models import Facture, Paiement
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC57-{_nxt():04d}',
            client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('500'),
            date_paiement=date.today(), mode=Paiement.Mode.VIREMENT)
        return Facture.objects.get(pk=facture.pk)

    def _pdf(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return self.objets[generate_facture_pdf(facture.id)]

    def test_totaux_dans_la_page(self):
        doc = _doc(self._pdf(self._facture(self.client_ar)))
        try:
            for page in doc:
                largeur = page.rect.width
                for x0, _y0, x1, _y1, texte, *_ in page.get_text('blocks'):
                    self.assertGreaterEqual(x0, 0, texte)
                    self.assertLessEqual(x1, largeur, texte)
        finally:
            doc.close()

    def test_montants_lisibles(self):
        facture = self._facture(self.client_ar)
        texte = _texte(self._pdf(facture))
        # CLAUSE CLIENT : mêmes montants que l'API.
        self.assertEqual(Decimal(str(facture.total_ttc)), Decimal('1200.00'))
        self.assertEqual(Decimal(str(facture.montant_du)), Decimal('700.00'))
        self.assertIn('1200.00', texte)
        self.assertIn('700.00', texte)

    def test_francais_inchange(self):
        from apps.ventes.utils.pdf import generate_facture_pdf  # noqa: F401
        texte = _texte(self._pdf(self._facture(self.client_fr)))
        self.assertIn('Total TTC 1200.00 MAD', texte)
        self.assertIn('Reste à payer 700.00 MAD', texte)
        # Le bloc AFAC57 n'existe que dans la page arabe.
        from django.template.loader import get_template  # noqa: F401
        from pathlib import Path
        gabarit = (Path(__file__).resolve().parents[3] / 'templates' / 'pdf'
                   / 'facture.html').read_text(encoding='utf-8')
        debut = gabarit.index('AFAC57')
        self.assertIn("{% if langue_document == 'ar' %}",
                      gabarit[max(0, debut - 200):debut])
