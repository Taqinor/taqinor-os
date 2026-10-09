"""APDF29 (C-APDF-009) — le pro-forma imprime une date de validité et les
coordonnées bancaires du BÉNÉFICIAIRE (RIB et banque du profil de SA société,
rien si vides), sans se présenter comme une demande de paiement.

Rejoue la sonde PCGV-568 (RIB, banque et validité absents). Vrai
``generate_proforma_pdf`` (rendu WeasyPrint réel), texte PyMuPDF, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_proforma_mentions"
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class ProformaMentionsTests(TestCase):
    def _societe(self, rib='', banque=''):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Devis, LigneDevis
        from authentication.models import Company
        n = _nxt()
        company = Company.objects.create(nom=f'APDF29 {n}', slug=f'apdf29-{n}')
        profile = CompanyProfile.get(company=company)
        profile.rib = rib
        profile.banque = banque
        profile.save()
        client = Client.objects.create(
            company=company, nom='Client', prenom='APDF29',
            email=f'apdf29-{n}@example.invalid')
        self.validite = date.today() + timedelta(days=20)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-APDF29-{n}', client=client,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_validite=self.validite)
        LigneDevis.objects.create(
            devis=devis, designation='Centrale', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        return devis

    def _pdf(self, devis):
        from apps.ventes.utils.pdf import generate_proforma_pdf
        return _texte(generate_proforma_pdf(devis, f'PF-TEST-{_nxt()}'))

    def test_validite_et_rib(self):
        texte = self._pdf(self._societe(
            rib='011 780 0000123456789012 34', banque='Banque Test'))
        self.assertIn(
            f"Valable jusqu'au {self.validite.strftime('%d/%m/%Y')}", texte)
        self.assertIn('011 780 0000123456789012 34', texte)
        self.assertIn('Banque Test', texte)

    def test_sans_rib_aucune_ligne(self):
        # Un autre tenant a un RIB : il n'apparaît jamais ici.
        self._societe(rib='999 999 9999999999999999 99', banque='Autre')
        texte = self._pdf(self._societe())
        self.assertNotIn('RIB', texte)
        self.assertNotIn('999 999', texte)

    def test_mention_indicative_conservee(self):
        texte = self._pdf(self._societe(rib='011 780', banque='B'))
        self.assertIn("n'engage aucune obligation de paiement", texte)
