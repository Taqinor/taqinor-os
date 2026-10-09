"""ACHT22 (C-ACHT-020) — le bon de livraison imprime l'adresse de livraison
SAISIE (`Livraison.adresse_site`, repli sur l'adresse du chantier) et un
bandeau « ANNULÉE » pour une livraison annulée.

Texte extrait du PDF réel (PyMuPDF) ; aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_bon_livraison"
"""
from django.test import TestCase

from authentication.models import Company

from apps.installations.livraison_pdf import bon_livraison_pdf
from apps.installations.models import Installation, Livraison


def _texte(pdf):
    import fitz
    doc = fitz.open(stream=pdf, filetype='pdf')
    brut = ''.join(p.get_text() for p in doc)
    return ' '.join(brut.replace('\xa0', ' ').split())


class BonLivraisonTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht22', defaults={'nom': 'Co ACHT22'})
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT22',
            site_adresse='Adresse chantier')

    def _livraison(self, ref, **kw):
        return Livraison.objects.create(
            company=self.company, installation=self.inst, reference=ref, **kw)

    def test_adresse_livraison_imprimee(self):
        liv = self._livraison(
            'LIV-ACHT22-1',
            adresse_site='Zone Industrielle Sidi Bernoussi, Casablanca')
        texte = _texte(bon_livraison_pdf(liv))
        self.assertIn('Zone Industrielle Sidi Bernoussi', texte)
        self.assertNotIn('Adresse chantier', texte)

    def test_repli_adresse_chantier(self):
        liv = self._livraison('LIV-ACHT22-2')
        texte = _texte(bon_livraison_pdf(liv))
        self.assertIn('Adresse chantier', texte)

    def test_bandeau_annulee(self):
        liv = self._livraison('LIV-ACHT22-3',
                              statut=Livraison.Statut.ANNULEE)
        self.assertIn('ANNULÉE', _texte(bon_livraison_pdf(liv)))
        liv_ok = self._livraison('LIV-ACHT22-4')
        self.assertNotIn('ANNULÉE', _texte(bon_livraison_pdf(liv_ok)))
