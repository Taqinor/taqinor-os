"""APDF28 (C-APDF-010) — pages numérotées (« Page i / N », traduit en arabe)
et référence du document + identité de l'émetteur (ICE) répétées sur CHAQUE
page de la facture, de l'avoir, de la note de débit et du bon de commande
(règle ``@page`` commune).

Rejoue la sonde PFAC-3 (pages intermédiaires sans référence, sans ICE, sans
numéro). Rendu WeasyPrint RÉEL ; seul l'upload MinIO est neutralisé.

Test-du-test : retirer la règle ``@page`` de ``facture.html`` ⇒
``test_facture_chaque_page`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_pagination"
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

ICE = '001234567000089'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _pages(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return [' '.join(page.get_text().split()) for page in doc]
    finally:
        doc.close()


class PaginationTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import Produit
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'APDF28 {n}', slug=f'apdf28-{n}')
        profil = CompanyProfile.get(company=self.company)
        profil.nom = 'Taqinor Pagination'
        profil.ice = ICE
        profil.rc = 'RC999'
        profil.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Berrada', prenom='Ali',
            email=f'apdf28-{n}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Module', sku=f'APDF28-{n}',
            prix_vente=Decimal('100'), quantite_stock=1000)
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _facture(self, nb_lignes, client=None):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-APDF28-{_nxt():04d}',
            client=client or self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'))
        for i in range(nb_lignes):
            LigneFacture.objects.create(
                facture=facture, produit=self.produit,
                designation=f'Module photovoltaïque {i + 1}',
                quantite=Decimal('1'), prix_unitaire=Decimal('100'),
                remise=Decimal('0'), taux_tva=Decimal('20'))
        return Facture.objects.get(pk=facture.pk)

    def _verifier(self, pages, reference, libelle='Page'):
        total = len(pages)
        for i, texte in enumerate(pages, start=1):
            with self.subTest(page=i):
                self.assertIn(f'{libelle} {i} / {total}', texte)
                self.assertIn(reference, texte)
                self.assertIn(ICE, texte)

    def test_facture_chaque_page(self):
        from apps.ventes.utils.pdf import generate_facture_pdf
        facture = self._facture(63)
        pages = _pages(self.objets[generate_facture_pdf(facture.id)])
        self.assertGreater(len(pages), 1)
        self._verifier(pages, facture.reference)

    def test_avoir_chaque_page(self):
        from apps.ventes.models import Avoir, LigneAvoir
        from apps.ventes.utils.pdf import generate_avoir_pdf
        facture = self._facture(1)
        avoir = Avoir.objects.create(
            company=self.company, reference=f'AV-APDF28-{_nxt():04d}',
            facture=facture, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20'))
        for i in range(60):
            LigneAvoir.objects.create(
                avoir=avoir, produit=self.produit,
                designation=f'Reprise module {i + 1}', quantite=Decimal('1'),
                prix_unitaire=Decimal('1'), remise=Decimal('0'),
                taux_tva=Decimal('20'))
        pages = _pages(self.objets[generate_avoir_pdf(avoir.id)])
        self.assertGreater(len(pages), 1)
        self._verifier(pages, avoir.reference)

    def test_une_page(self):
        from apps.ventes.utils.pdf import generate_facture_pdf
        facture = self._facture(1)
        pages = _pages(self.objets[generate_facture_pdf(facture.id)])
        self.assertEqual(len(pages), 1)
        self._verifier(pages, facture.reference)

    def test_libelle_ar(self):
        from apps.crm.models import Client
        from apps.ventes.utils.libelles_ar import LIBELLES
        client_ar = Client.objects.create(
            company=self.company, nom='Berrada', prenom='Lina',
            email=f'apdf28-ar-{_nxt()}@example.invalid',
            langue_document='ar')
        facture = self._facture(1, client=client_ar)
        capture = []
        from apps.ventes.utils import pdf as pdf_mod
        vrai = pdf_mod._render_html
        with patch('apps.ventes.utils.pdf._render_html',
                   side_effect=lambda n, c: capture.append(vrai(n, c))
                   or capture[-1]):
            pdf_mod.generate_facture_pdf(facture.id)
        self.assertIn(f'"{LIBELLES["ar"]["page"]} " counter(page)',
                      capture[-1])
