"""XPOS18 — Pont matériel comptoir : ESC/POS + tiroir-caisse + TPE.

Couvre : le flux ESC/POS généré contient identité société/lignes TTC/TVA/
coupe/impulsion tiroir (octets vérifiés), sans config aucune connexion
sortante n'est tentée, tests multi-tenant.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import escpos, receipt, services
from apps.pos.models import ConfigMaterielPOS, LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class EscposBuildTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos18', 'XPOS18 Co')
        self.user = make_user(self.co, 'caissier-xpos18')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur', prix_vente=Decimal('1200'),
            quantite_stock=5, categorie=categorie)
        self.vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-XPOS18-1', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=self.vente, produit=self.produit, designation='Onduleur',
            quantite=1, prix_unitaire_ttc=Decimal('1200'))
        services.valider_vente(
            vente=self.vente, paiements=[{'mode': 'carte', 'montant': '1200'}],
            user=self.user)
        self.identite = receipt._company_identity(self.co)

    def test_escpos_contains_identity_and_lines(self):
        payload = escpos.build_ticket_escpos(
            self.vente, identite=self.identite)
        self.assertIn(self.identite['nom'].encode('cp437'), payload)
        self.assertIn(b'Onduleur', payload)

    def test_escpos_contains_cut_and_drawer_kick(self):
        payload = escpos.build_ticket_escpos(
            self.vente, identite=self.identite)
        self.assertIn(escpos.CUT, payload)
        self.assertIn(escpos.CASH_DRAWER_KICK, payload)

    def test_escpos_contains_tva_breakdown(self):
        payload = escpos.build_ticket_escpos(
            self.vente, identite=self.identite)
        self.assertIn(b'TVA', payload)

    def test_escpos_references_facture(self):
        payload = escpos.build_ticket_escpos(
            self.vente, identite=self.identite)
        self.assertIn(self.vente.facture.reference.encode('cp437'), payload)


class SendToPrinterGatingTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos18-net', 'XPOS18 Net Co')

    def test_no_config_is_noop(self):
        sent = escpos.send_to_printer(b'payload', config=None)
        self.assertFalse(sent)

    def test_inactive_config_is_noop(self):
        config = ConfigMaterielPOS.objects.create(
            company=self.co, imprimante_ip='10.0.0.5', imprimante_active=False)
        sent = escpos.send_to_printer(b'payload', config=config)
        self.assertFalse(sent)

    def test_active_without_ip_is_noop(self):
        config = ConfigMaterielPOS.objects.create(
            company=self.co, imprimante_ip='', imprimante_active=True)
        sent = escpos.send_to_printer(b'payload', config=config)
        self.assertFalse(sent)

    def test_active_with_closed_port_fails_gracefully(self):
        # 127.0.0.1 sur un port fermé : connexion refusée IMMÉDIATEMENT (pas
        # de délai réseau) — vérifie que l'échec est avalé sans exception.
        config = ConfigMaterielPOS.objects.create(
            company=self.co, imprimante_ip='127.0.0.1', imprimante_port=1,
            imprimante_active=True)
        sent = escpos.send_to_printer(b'payload', config=config)
        self.assertFalse(sent)
