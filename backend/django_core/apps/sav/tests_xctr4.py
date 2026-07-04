"""XCTR4 — Routage de couverture (garantie / contrat O&M / facturable).

Couvre :
  * calcul de couverture testé sur les 3 chemins (garantie / contrat /
    facturable) ;
  * l'action `facturer` émet une facture 0 DH quand couvert, réelle sinon ;
  * aucune fuite de `prix_achat` dans la facture générée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xctr4 -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import ContratMaintenance, Equipement, PieceConsommee, Ticket
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug='sav-xctr4', nom='Sav Co XCTR4'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XCTR4CouvertureRoutageTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xctr4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XCTR4',
            email='xctr4-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XCTR4', client=self.client_obj)
        self.piece = Produit.objects.create(
            company=self.company, nom='Fusible XCTR4', sku='FUS-XCTR4',
            prix_achat=Decimal('5'), prix_vente=Decimal('50'))

    def test_couverture_garantie(self):
        produit_eq = Produit.objects.create(
            company=self.company, nom='Onduleur XCTR4', sku='OND-XCTR4',
            prix_achat=100, prix_vente=200, garantie_mois=24)
        equip = Equipement.objects.create(
            company=self.company, produit=produit_eq, installation=self.inst,
            date_pose=date.today() - timedelta(days=30),
            created_by=self.admin)
        equip.recompute_garanties()
        equip.save(update_fields=['date_fin_garantie', 'date_fin_garantie_production'])
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-1',
            client=self.client_obj, installation=self.inst, equipement=equip,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.GARANTIE)

    def test_couverture_contrat_quota_disponible(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1), actif=True,
            deplacements_inclus_an=5)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-2',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, date_ouverture=date(2026, 3, 1),
            created_by=self.admin)
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.CONTRAT)

    def test_couverture_facturable_quota_epuise(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1), actif=True,
            deplacements_inclus_an=1)
        Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-3A',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, date_ouverture=date(2026, 1, 15),
            created_by=self.admin)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-3B',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, date_ouverture=date(2026, 3, 1),
            created_by=self.admin)
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.FACTURABLE)
        self.assertIsNotNone(contrat)

    def test_couverture_facturable_sans_contrat_ni_garantie(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-4',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)
        self.assertEqual(
            ticket.couverture_calculee(), Ticket.Couverture.FACTURABLE)

    def test_action_facturer_facturable_facture_reelle(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-5',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, couverture=Ticket.Couverture.FACTURABLE,
            created_by=self.admin)
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=self.piece, quantite=2)
        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{ticket.pk}/facturer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        ligne = LigneFacture.objects.get(facture=facture, produit=self.piece)
        self.assertEqual(ligne.prix_unitaire, Decimal('50.00'))
        # Jamais de fuite de prix_achat dans la facture.
        self.assertNotEqual(ligne.prix_unitaire, self.piece.prix_achat)

    def test_action_facturer_couvert_facture_zero(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1), actif=True)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR4-6',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, date_ouverture=date(2026, 3, 1),
            created_by=self.admin)
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=self.piece, quantite=1)
        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{ticket.pk}/facturer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['couverture'], Ticket.Couverture.CONTRAT)
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        ligne = LigneFacture.objects.get(facture=facture, produit=self.piece)
        self.assertEqual(ligne.prix_unitaire, Decimal('0'))
