"""XSTK18 — Bon de livraison (N22) bilingue FR/AR (RTL) selon
`Client.langue_document`.

N93 a livré l'i18n de l'UI + `Client.langue_document`, mais le rendu PDF
arabe restait un « follow-on » jamais planifié — le BL ne sortait qu'en
français. Ce test vérifie :
  - un client `langue_document='ar'` reçoit un BL arabe RTL correct (gabarit
    dédié `document_bon_livraison_ar.html`) ;
  - un client `langue_document='fr'` (ou par défaut) reçoit l'existant
    inchangé (gabarit historique `document_bon_livraison.html`, jamais
    modifié par cette tâche) ;
  - aucun prix d'achat ne fuite dans le rendu arabe.

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_xstk18_bon_livraison_arabe -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

BUY_PRICE_MARKER = '888.88'


def _company(slug='xstk18-co', nom='XSTK18 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def _client(company, langue='fr'):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Nadia',
        telephone='+212600000099', adresse='5 rue Test, Rabat',
        langue_document=langue,
    )


def _produit(company):
    return Produit.objects.create(
        company=company, nom='Onduleur hybride', sku='OND-XSTK18',
        prix_vente=Decimal('9000.00'),
        prix_achat=Decimal(BUY_PRICE_MARKER),
        quantite_stock=5, marque='Deye',
        garantie='10 ans',
    )


def _devis(company, client_obj, produit):
    devis = Devis.objects.create(
        company=company, reference='DEV-XSTK18-0001', client=client_obj,
        statut='accepte', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'),
    )
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Onduleur hybride',
        quantite=Decimal('1'), prix_unitaire=Decimal('9000.00'),
        remise=Decimal('0'),
    )
    return devis


def _chantier(company, client_obj, devis, ref):
    return Installation.objects.create(
        company=company, reference=ref, client=client_obj, devis=devis,
        puissance_installee_kwc=Decimal('5.00'),
        date_mise_en_service='2026-06-01',
        date_pose_reelle='2026-05-28',
        site_adresse='5 rue Test', site_ville='Rabat',
    )


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class TestBonLivraisonArabe(TestCase):

    def setUp(self):
        self.company = _company()
        self.produit = _produit(self.company)

    def _captured_html(self, mock_html_to_pdf):
        return mock_html_to_pdf.call_args[0][0]

    def test_ar_client_renders_arabic_rtl_via_dedicated_template(
            self, mock_pdf, _dl):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        client_ar = _client(self.company, langue='ar')
        devis = _devis(self.company, client_ar, self.produit)
        chantier = _chantier(self.company, client_ar, devis, 'CH-XSTK18-AR')

        builders.generate_bon_livraison(chantier)
        html = self._captured_html(mock_pdf)

        self.assertIn('dir="rtl"', html)
        self.assertIn('lang="ar"', html)
        self.assertIn('إذن التسليم', html)
        self.assertIn('التسليم إلى', html)

    def test_fr_client_renders_existing_template_byte_identical(
            self, mock_pdf, _dl):
        from apps.documents import builders
        from django.template.loader import get_template

        mock_pdf.return_value = b'%PDF-fake'
        client_fr = _client(self.company, langue='fr')
        devis = _devis(self.company, client_fr, self.produit)
        chantier = _chantier(self.company, client_fr, devis, 'CH-XSTK18-FR')

        builders.generate_bon_livraison(chantier)
        html_via_builder = self._captured_html(mock_pdf)

        # Rendu direct du gabarit historique inchangé, avec le même contexte
        # que `generate_bon_livraison` construisait AVANT cette tâche (pas de
        # clé `L`/`arabic_font_face_css` posée côté FR) — les deux doivent
        # matcher à l'octet près.
        ctx = builders._base_context(chantier)
        ctx['composants'] = builders._composants(chantier)
        ctx['date_livraison'] = (
            builders._as_date(chantier.date_pose_reelle)
            or builders._as_date(chantier.date_mise_en_service)
        )
        expected = get_template('document_bon_livraison.html').render(ctx)
        self.assertEqual(html_via_builder, expected)
        self.assertNotIn('dir="rtl"', html_via_builder)

    def test_default_langue_document_renders_french(self, mock_pdf, _dl):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        # Aucune langue explicite posée → défaut historique FR (Client model).
        client_obj = Client.objects.create(
            company=self.company, nom='Bennis', prenom='Omar',
            telephone='+212600000098',
        )
        devis = _devis(self.company, client_obj, self.produit)
        chantier = _chantier(
            self.company, client_obj, devis, 'CH-XSTK18-DEFAULT')

        builders.generate_bon_livraison(chantier)
        html = self._captured_html(mock_pdf)
        self.assertIn('BON DE LIVRAISON', html)
        self.assertNotIn('dir="rtl"', html)

    def test_ar_render_never_leaks_buy_price(self, mock_pdf, _dl):
        mock_pdf.return_value = b'%PDF-fake'
        from apps.documents import builders
        client_ar = _client(self.company, langue='ar')
        devis = _devis(self.company, client_ar, self.produit)
        chantier = _chantier(
            self.company, client_ar, devis, 'CH-XSTK18-PRICE')

        builders.generate_bon_livraison(chantier)
        html = self._captured_html(mock_pdf)
        self.assertNotIn(BUY_PRICE_MARKER, html)
