# -*- coding: utf-8 -*-
"""ATOT11 — facture, avoir et note de débit impriment la chaîne COMPLÈTE
Sous-total HT → Remise → Arrondi → **Total HT** → TVA par taux → TTC, par
UNE macro Jinja partagée (``templates/pdf/_chaine_totaux.html``).

Constat C-ATOT-017 (sonde V2 TSORT-4) : sur une facture remisée, la base
nette ``ht_net`` n'apparaissait nulle part dans le texte du PDF — le lecteur
voyait « Sous-total − Remise » puis la TVA, sans la base sur laquelle la TVA
est calculée.

Scénario FAC-DEMO-0002 : une ligne 5 820,00 HT à 20 %, ``remise_globale = 5``
→ remise 291,00, Total HT 5 529,00, TVA 1 105,80, TTC 6 634,80.

Source réelle : ``utils/pdf.generate_*_pdf`` (rendu WeasyPrint réel), texte lu
par PyMuPDF ; seul l'upload MinIO (``_upload_pdf``) et le logo sont neutralisés.

Test-du-test : retirer la ligne Total HT de la macro ⇒ les trois tests
échouent.
"""
import re
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Avoir, Facture, LigneAvoir, LigneFacture, LigneNoteDebit, NoteDebit,
)
from authentication.models import Company

User = get_user_model()

_N = r'([0-9]+\.[0-9]{2})'


def _texte_pdf(octets):
    import fitz  # PyMuPDF
    with fitz.open(stream=octets, filetype='pdf') as doc:
        texte = '\n'.join(page.get_text() for page in doc)
    return re.sub(r'\s+', ' ', texte)


def _capturer_pdf():
    """Renvoie (patch, boîte) : la boîte reçoit les octets PDF uploadés."""
    boite = {}

    def _upload(pdf_bytes, key):
        boite['pdf'] = pdf_bytes

    return patch('apps.ventes.utils.pdf._upload_pdf', side_effect=_upload), boite


@patch('apps.ventes.utils.pdf._download', return_value=None)
class PdfChaineTotauxTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='atot11-co', defaults={'nom': 'ATOT11 Co'})
        self.user = User.objects.create_user(
            username='atot11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Chaine', prenom='ATOT11',
            telephone='+212600000011')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit solaire', prix_vente=Decimal('5820'),
            quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, client=self.client_obj,
            reference='FAC-DEMO-0002', statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Kit solaire', quantite=Decimal('1'),
            prix_unitaire=Decimal('5820'), taux_tva=Decimal('20.00'))

    def _texte(self, generer, pk):
        patcheur, boite = _capturer_pdf()
        with patcheur:
            generer(pk)
        return _texte_pdf(boite['pdf'])

    def _verifier_chaine(self, texte, libelle_ttc):
        motif = (
            r'Sous-total HT[^0-9]*?' + _N + r' MAD'
            r'.*?Remise globale \([0-9.]+ ?%\) [−-] ?' + _N + r' MAD'
            r'.*?Total HT ' + _N + r' MAD'
            r'.*?TVA \([0-9.]+%\) ' + _N + r' MAD'
            r'.*?' + re.escape(libelle_ttc) + r' ' + _N + r' MAD')
        trouve = re.search(motif, texte)
        self.assertIsNotNone(trouve, texte[-1200:])
        sous_total, remise, total_ht, tva, ttc = (
            Decimal(x) for x in trouve.groups())
        self.assertEqual(sous_total, Decimal('5820.00'))
        self.assertEqual(remise, Decimal('291.00'))
        self.assertEqual(total_ht, Decimal('5529.00'))
        # Sous-total − Remise − Arrondi (0) = Total HT ; Total HT + Σ TVA = TTC.
        self.assertEqual(sous_total - remise, total_ht)
        self.assertEqual(total_ht + tva, ttc)
        self.assertEqual(ttc, Decimal('6634.80'))
        self.assertIn('Total HT 5529.00 MAD', texte)

    def test_facture(self, _dl):
        from apps.ventes.utils.pdf import generate_facture_pdf
        texte = self._texte(generate_facture_pdf, self.facture.id)
        self._verifier_chaine(texte, 'Total TTC')

    def test_avoir(self, _dl):
        from apps.ventes.utils.pdf import generate_avoir_pdf
        avoir = Avoir.objects.create(
            company=self.company, client=self.client_obj,
            facture=self.facture, reference='AV-DEMO-0002',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'))
        LigneAvoir.objects.create(
            avoir=avoir, produit=self.produit, designation='Kit solaire',
            quantite=Decimal('1'), prix_unitaire=Decimal('5820'),
            taux_tva=Decimal('20.00'))
        texte = self._texte(generate_avoir_pdf, avoir.id)
        self._verifier_chaine(texte, 'Total crédité TTC')

    def test_note_debit(self, _dl):
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        note = NoteDebit.objects.create(
            company=self.company, client=self.client_obj,
            facture=self.facture, reference='ND-DEMO-0002',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'))
        LigneNoteDebit.objects.create(
            note_debit=note, produit=self.produit, designation='Kit solaire',
            quantite=Decimal('1'), prix_unitaire=Decimal('5820'),
            taux_tva=Decimal('20.00'))
        texte = self._texte(generate_note_debit_pdf, note.id)
        self._verifier_chaine(texte, 'Total dû en supplément (TTC)')
