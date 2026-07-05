"""XSAL13 — Documents client en arabe (facture legacy) selon
`Client.langue_document`.

Le devis one-page premium (moteur `apps/ventes/quote_engine/`) est HORS
PÉRIMÈTRE de cette lane (règle #4, revue dédiée) — cette tâche couvre
uniquement la facture legacy (`templates/pdf/facture.html`).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal13_facture_arabe -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.utils.libelles_ar import libelle, document_langue
from apps.ventes.utils.pdf import _company_context, _render_html

User = get_user_model()


def make_company(slug='xsal13-co', nom='XSAL13 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestLibellesAr(TestCase):
    def test_fr_default_matches_historical_literal(self):
        self.assertEqual(libelle('facture', 'fr'), 'FACTURE')
        self.assertEqual(libelle('facture'), 'FACTURE')  # défaut langue='fr'

    def test_ar_translation_present(self):
        self.assertEqual(libelle('facture', 'ar'), 'فاتورة')
        self.assertEqual(libelle('total_ttc', 'ar'), 'المجموع شامل الضريبة')

    def test_unknown_key_falls_back_to_key_itself(self):
        self.assertEqual(libelle('cle_inconnue', 'ar'), 'cle_inconnue')

    def test_document_langue_defaults_to_fr(self):
        class FauxClient:
            pass
        self.assertEqual(document_langue(FauxClient()), 'fr')


@tag('pdf')
class TestFactureRenderArabic(TestCase):
    """Rendu réel (WeasyPrint non requis ici — seulement _render_html/Jinja)."""

    def setUp(self):
        self.company = make_company()
        self.client_fr = Client.objects.create(
            company=self.company, nom='Dupont', prenom='Jean',
            telephone='+212600000010', langue_document='fr')
        self.client_ar = Client.objects.create(
            company=self.company, nom='Alami', prenom='Youssef',
            telephone='+212600000011', langue_document='ar')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-XSAL13',
            prix_vente=Decimal('5000'), tva=Decimal('20.00'))

    def _make_facture(self, client_obj, ref):
        facture = Facture.objects.create(
            company=self.company, reference=ref, client=client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        return facture

    def _render(self, facture):
        from apps.ventes.utils.libelles_ar import (
            document_langue, libelle, arabic_font_face_css,
        )
        ctx = _company_context(company=self.company)
        ctx['facture'] = facture
        langue = document_langue(facture.client)
        ctx['langue_document'] = langue
        ctx['L'] = lambda cle: libelle(cle, langue)
        ctx['arabic_font_face_css'] = arabic_font_face_css() if langue == 'ar' else ''
        return _render_html('facture.html', ctx)

    def test_fr_client_renders_byte_identical_labels(self):
        facture = self._make_facture(self.client_fr, 'FAC-XSAL13-0001')
        html = self._render(facture)
        self.assertIn('FACTURE', html)
        self.assertIn('Émetteur', html)
        self.assertIn('Sous-total HT', html)
        self.assertIn('lang="fr"', html)
        self.assertNotIn('dir="rtl"', html)

    def test_ar_client_renders_arabic_rtl(self):
        facture = self._make_facture(self.client_ar, 'FAC-XSAL13-0002')
        html = self._render(facture)
        self.assertIn('فاتورة', html)
        self.assertIn('المجموع شامل الضريبة', html)
        self.assertIn('dir="rtl"', html)
        self.assertIn('lang="ar"', html)

    def test_ar_client_amounts_stay_western_digits_mad(self):
        facture = self._make_facture(self.client_ar, 'FAC-XSAL13-0003')
        html = self._render(facture)
        # Montants en chiffres occidentaux + MAD, jamais convertis.
        self.assertIn('5000.00 MAD', html)

    def test_missing_context_vars_never_raise(self):
        """Un ancien appelant qui construit son propre dict (sans L/langue)
        continue de rendre le FR historique — jamais d'UndefinedError."""
        facture = self._make_facture(self.client_fr, 'FAC-XSAL13-0004')
        ctx = {
            'facture': facture, 'entreprise_nom': 'ACME', 'entreprise_adresse': '',
            'entreprise_email': '', 'entreprise_telephone': '', 'entreprise_siret': '',
            'entreprise_tva_intra': '', 'couleur_principale': '#000', 'logo_uri': None,
            'signature_uri': None, 'rib': '', 'banque': '',
        }
        html = _render_html('facture.html', ctx)
        self.assertIn('FACTURE', html)

    def test_never_exposes_prix_achat(self):
        facture = self._make_facture(self.client_ar, 'FAC-XSAL13-0005')
        html = self._render(facture)
        self.assertNotIn('prix_achat', html)


class TestGenerateFacturePdfLanguageWiring(TestCase):
    """Vérifie que generate_facture_pdf pose bien langue_document/L selon le
    client, sans appeler MinIO (mocké)."""

    def setUp(self):
        self.company = make_company(slug='xsal13-wire-co', nom='XSAL13 Wire Co')
        self.user = User.objects.create_user(
            username='xsal13user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_ar = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Sara',
            telephone='+212600000012', langue_document='ar')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-XSAL13',
            prix_vente=Decimal('900'), tva=Decimal('10.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-XSAL13-WIRE-0001',
            client=self.client_ar, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('900'),
            taux_tva=Decimal('10.00'))

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_generate_facture_pdf_still_succeeds_for_ar_client(self, mock_dl, mock_upload):
        from apps.ventes.utils.pdf import generate_facture_pdf
        key = generate_facture_pdf(self.facture.id)
        self.assertEqual(key, f'factures/{self.facture.reference}.pdf')
        mock_upload.assert_called_once()
        pdf_bytes_arg = mock_upload.call_args[0][0]
        self.assertTrue(pdf_bytes_arg[:4] == b'%PDF')
