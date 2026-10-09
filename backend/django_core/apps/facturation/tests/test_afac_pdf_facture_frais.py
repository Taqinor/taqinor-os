"""AFAC41 (C-AFAC-042) — le téléchargement interne du PDF facture
(``telecharger-pdf``, donc aussi l'aperçu inline de la liste) sert le PDF
GARANTI à jour par ``cle_facture_pdf_a_jour``, comme le lien public.

Rejoue les sondes L2-C-AFAC-042 (« Reste à payer 900.00 » au lieu de 400.00 ;
brouillon modifié imprimé 1 200.00 au lieu de 2 400) et FDOC-2 (octets d'avant
paiement). APIClient, rendu WeasyPrint RÉEL ; seule l'I/O MinIO est simulée
(un dict en mémoire).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_pdf_facture_frais"
"""
import re
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte_pdf(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        texte = '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()
    # Séparateurs de milliers (espace fine / insécable) neutralisés.
    return re.sub(r'(?<=\d)[\s  ](?=\d{3}\b)', '', texte)


class TelechargementPdfFraisTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC41 Co', slug=f'afac41-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac41-resp-{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Salma',
            email=f'afac41-{_nxt()}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'AFAC41-{_nxt()}',
            prix_vente=Decimal('1000'))
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_dl = patch('apps.ventes.utils.pdf.download_pdf',
                     side_effect=lambda k: self.objets[k])
        p_up.start()
        p_dl.start()
        self.addCleanup(p_up.stop)
        self.addCleanup(p_dl.stop)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _facture(self, statut):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC41-{_nxt():04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20.00'))
        ligne = LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return facture, ligne

    def _payer(self, facture, montant, jour):
        from apps.ventes.models import Paiement
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=jour, mode=Paiement.Mode.VIREMENT)

    def _telecharger(self, facture):
        r = self.api.get(
            f'/api/django/ventes/factures/{facture.id}/telecharger-pdf/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        return b''.join(r.streaming_content) if r.streaming else r.content

    def test_telecharger_apres_paiement_reste_courant(self):
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour
        facture, _ = self._facture('emise')
        self._payer(facture, '300', date(2026, 9, 1))
        cle = cle_facture_pdf_a_jour(facture)  # « Générer PDF »
        self.assertIn('900.00', _texte_pdf(self.objets[cle]))
        self._payer(facture, '500', date(2026, 9, 15))
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('400.00'))
        texte = _texte_pdf(self._telecharger(facture))
        self.assertIn('Reste à payer', texte)
        self.assertIn('400.00', texte)
        self.assertNotIn('900.00', texte)
        # CLAUSE PERSISTANCE : un second téléchargement sans changement ne
        # re-rend pas (même clé, même empreinte).
        facture.refresh_from_db()
        empreinte = facture.pdf_render_meta.get('empreinte')
        with patch('apps.ventes.utils.pdf.generate_facture_pdf') as rendu:
            self._telecharger(facture)
            rendu.assert_not_called()
        facture.refresh_from_db()
        self.assertEqual(facture.pdf_render_meta.get('empreinte'), empreinte)

    def test_telecharger_brouillon_ligne_modifiee(self):
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour
        facture, ligne = self._facture('brouillon')
        cle_facture_pdf_a_jour(facture)
        r = self.api.patch(
            f'/api/django/ventes/factures-lignes/{ligne.id}/',
            {'quantite': '2'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.total_ttc, Decimal('2400.00'))
        texte = _texte_pdf(self._telecharger(facture))
        self.assertIn('2400.00', texte)

    def test_telecharger_jamais_rendue(self):
        facture, _ = self._facture('emise')
        self.assertFalse(facture.fichier_pdf)
        contenu = self._telecharger(facture)
        self.assertTrue(contenu.startswith(b'%PDF'))
