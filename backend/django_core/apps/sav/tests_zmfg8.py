"""ZMFG8 — Typage opérationnel des pièces sur ticket : Ajout / Retrait /
Recyclage (parité Repair Parts tab Odoo).

Couvre :
  * `PieceConsommee.operation` == 'ajout' (toujours) ;
  * `PieceRetiree.operation` explicite retrait/recyclage, défaut retrait ;
  * recyclage SANS destination stock_occasion → refusé (ValueError côté
    service, 400 côté API) ;
  * recyclage AVEC destination stock_occasion → accepté, restock inchangé
    (toujours géré par XMFG10) ;
  * la liste unifiée (`selectors.pieces_unifiees`) affiche les 3 types avec
    sous-totaux exacts.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg8 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import PieceConsommee, PieceRetiree, Ticket
from apps.sav.selectors import pieces_unifiees
from apps.sav.services import OperationDestinationIncoherenteError, retirer_piece

User = get_user_model()


def make_company(slug='sav-zmfg8', nom='Sav Co ZMFG8'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG8OperationTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg8_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG8',
            email='zmfg8-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG8', client=self.client_obj)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ZMFG8', sku='OND-ZMFG8',
            prix_achat=3000, prix_vente=6000, quantite_stock=Decimal('2'))
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ZMFG8-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def test_piece_consommee_operation_is_always_ajout(self):
        piece = PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('2'))
        self.assertEqual(piece.operation, 'ajout')

    def test_piece_retiree_defaults_to_retrait(self):
        piece = retirer_piece(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='', destination='rebut',
            user=self.admin)
        self.assertEqual(piece.operation, PieceRetiree.Operation.RETRAIT)

    def test_recyclage_without_stock_occasion_is_rejected(self):
        with self.assertRaises(OperationDestinationIncoherenteError):
            retirer_piece(
                company=self.company, ticket=self.ticket, produit=self.onduleur,
                quantite=Decimal('1'), numero_serie='', destination='rebut',
                operation='recyclage', user=self.admin)
        self.assertEqual(PieceRetiree.objects.count(), 0)

    def test_recyclage_with_stock_occasion_is_accepted(self):
        piece = retirer_piece(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='',
            destination='stock_occasion', operation='recyclage',
            user=self.admin)
        self.assertEqual(piece.operation, PieceRetiree.Operation.RECYCLAGE)
        self.assertTrue(piece.restockee)

    def test_api_rejects_recyclage_without_stock_occasion(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/pieces-retirees/',
            {'produit': self.onduleur.pk, 'quantite': 1,
             'destination': 'rebut', 'operation': 'recyclage'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unified_list_shows_all_three_types_with_subtotals(self):
        PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('3'))
        retirer_piece(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='', destination='rebut',
            user=self.admin)
        retirer_piece(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='',
            destination='stock_occasion', operation='recyclage',
            user=self.admin)

        data = pieces_unifiees(self.ticket)
        self.assertEqual(len(data['lignes']), 3)
        operations = sorted(row['operation'] for row in data['lignes'])
        self.assertEqual(operations, ['ajout', 'recyclage', 'retrait'])
        self.assertEqual(data['sous_totaux']['ajout'], Decimal('3'))
        self.assertEqual(data['sous_totaux']['retrait'], Decimal('1'))
        self.assertEqual(data['sous_totaux']['recyclage'], Decimal('1'))

    def test_unified_list_endpoint(self):
        PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'))
        resp = self.api.get(
            f'/api/django/sav/tickets/{self.ticket.pk}/pieces-unifiees/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['lignes']), 1)
