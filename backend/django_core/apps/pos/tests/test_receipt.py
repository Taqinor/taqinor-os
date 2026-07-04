"""XPOS3 — Ticket de caisse conforme (PDF 80 mm) + lien public tokenisé.

Couvre : ticket PDF conforme généré à la validation (mentions légales art.
145 CGI présentes), lien public tokenisé fonctionnel + expirant, jamais de
prix_achat.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.pos import receipt, services
from apps.pos.models import LigneVenteComptoir, ShareLinkTicket, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_session_caisse(company, user):
    """Ouvre une session de caisse (XPOS4) — requise pour tout règlement
    espèces (cf. services.valider_vente)."""
    compta_services.seed_plan_comptable(company)
    compta_services.seed_journaux(company)
    compte_caisse = CompteTresorerie.objects.create(
        company=company, type_compte=CompteTresorerie.Type.CAISSE,
        libelle='Caisse comptoir',
        compte_comptable=compta_services.get_compte(company, '5161'))
    caisse_comptable = compta_services.creer_caisse(
        company, compte_caisse, libelle='Caisse POS', solde_initial=Decimal('0'))
    return services.ouvrir_session(
        company=company, caisse_comptable=caisse_comptable,
        caissier=user, fond_ouverture=Decimal('0'), user=user)


class ReceiptHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos3', 'XPOS3 Co')
        self.user = make_user(self.co, 'caissier-xpos3')
        profile = CompanyProfile.get(company=self.co)
        profile.nom = 'TAQINOR SARL'
        profile.ice = 'ICE123'
        profile.identifiant_fiscal = 'IF456'
        profile.rc = 'RC789'
        profile.patente = 'PAT000'
        profile.cnss = 'CNSS111'
        profile.save()
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie', prix_vente=Decimal('500'),
            prix_achat=Decimal('300'), quantite_stock=10, categorie=categorie)
        session = make_session_caisse(self.co, self.user)
        self.vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-XPOS3-1', client=self.client_obj,
            created_by=self.user, session_caisse=session)
        LigneVenteComptoir.objects.create(
            vente=self.vente, produit=self.produit, designation='Batterie',
            quantite=1, prix_unitaire_ttc=Decimal('500'))
        services.valider_vente(
            vente=self.vente, paiements=[{'mode': 'especes', 'montant': '500'}],
            user=self.user)
        self.vente.refresh_from_db()

    def test_receipt_html_contains_legal_mentions(self):
        paiements = self.vente.facture.paiements.all()
        html = receipt.receipt_html(self.vente, paiements=paiements)
        self.assertIn('TAQINOR SARL', html)
        self.assertIn('ICE123', html)
        self.assertIn('IF456', html)
        self.assertIn('RC789', html)
        self.assertIn('PAT000', html)
        self.assertIn('CNSS111', html)
        self.assertIn(self.vente.facture.reference, html)

    def test_receipt_html_never_contains_prix_achat(self):
        html = receipt.receipt_html(self.vente)
        self.assertNotIn('300', html)  # prix_achat value

    def test_receipt_pdf_generates_bytes(self):
        pdf_bytes = receipt.receipt_pdf(self.vente)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))


class ShareLinkTicketTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos3-link', 'XPOS3 Link Co')
        self.user = make_user(self.co, 'caissier-xpos3-link')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble', prix_vente=Decimal('50'),
            quantite_stock=10, categorie=categorie)
        self.vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-XPOS3-2', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=self.vente, produit=self.produit, designation='Câble',
            quantite=1, prix_unitaire_ttc=Decimal('50'))
        services.valider_vente(
            vente=self.vente, paiements=[{'mode': 'carte', 'montant': '50'}],
            user=self.user)

    def test_for_vente_creates_and_reuses(self):
        link1 = ShareLinkTicket.for_vente(self.vente)
        link2 = ShareLinkTicket.for_vente(self.vente)
        self.assertEqual(link1.id, link2.id)
        self.assertTrue(link1.is_valid)

    def test_expired_link_not_reused(self):
        link = ShareLinkTicket.objects.create(
            company=self.co, vente=self.vente,
            expires_at=timezone.now() - timedelta(days=1))
        self.assertFalse(link.is_valid)
        new_link = ShareLinkTicket.for_vente(self.vente)
        self.assertNotEqual(link.id, new_link.id)

    def test_public_pdf_endpoint(self):
        link = ShareLinkTicket.for_vente(self.vente)
        resp = self.client.get(f'/api/django/public/pos/ticket/{link.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_public_pdf_endpoint_invalid_token(self):
        resp = self.client.get('/api/django/public/pos/ticket/does-not-exist/')
        self.assertEqual(resp.status_code, 404)

    def test_public_pdf_endpoint_expired_token(self):
        link = ShareLinkTicket.objects.create(
            company=self.co, vente=self.vente,
            expires_at=timezone.now() - timedelta(days=1))
        resp = self.client.get(f'/api/django/public/pos/ticket/{link.token}/')
        self.assertEqual(resp.status_code, 404)
