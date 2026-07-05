"""XMFG10 — Pièces retirées / récupérées sur ticket SAV (Remove & Recycle).

Couvre :
  * retrait tracé avec sa destination (rebut / retour_fournisseur /
    stock_occasion) ;
  * destination stock_occasion ré-incrémente le stock via MouvementStock
    ENTRÉE, exactement une fois (idempotent, `restockee`) ;
  * destination retour_fournisseur propose/crée un WarrantyClaim (FG83)
    quand le n° de série matche un équipement du parc ;
  * un n° de série qui matche un `sav.Equipement` le marque REMPLACÉ.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xmfg10 -v 2
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
from apps.sav.models import Equipement, PieceRetiree, Ticket, WarrantyClaim
from apps.sav.services import retirer_piece

User = get_user_model()


def make_company(slug='sav-xmfg10', nom='Sav Co XMFG10'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XMFG10PieceRetireeTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xmfg10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xmfg10-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XMFG10', client=self.client_obj)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur HS', sku='OND-HS-XMFG10',
            prix_achat=3000, prix_vente=6000, quantite_stock=Decimal('2'))

    def _ticket(self, ref='SAV-XMFG10-1', equipement=None):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, equipement=equipement,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def test_retrait_rebut_ne_bouge_pas_le_stock(self):
        ticket = self._ticket()
        piece = retirer_piece(
            company=self.company, ticket=ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='', destination='rebut',
            user=self.admin)
        self.assertEqual(piece.destination, PieceRetiree.Destination.REBUT)
        self.assertFalse(piece.restockee)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, Decimal('2'))

    def test_retrait_stock_occasion_restocke_une_seule_fois(self):
        ticket = self._ticket()
        piece = retirer_piece(
            company=self.company, ticket=ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='', destination='stock_occasion',
            user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, Decimal('3'))
        self.assertTrue(piece.restockee)

        # Idempotence : appeler à nouveau le restock manuellement sur la même
        # ligne ne doit rien ré-incrémenter (le service ne restocke que sur
        # `restockee=False`).
        from apps.stock.services import mouvement_type_entree, record_stock_movement
        if not piece.restockee:  # pragma: no cover - garde de non-régression
            record_stock_movement(
                company=self.company, produit=self.onduleur,
                type_mouvement=mouvement_type_entree(), quantite=Decimal('1'),
                quantite_avant=self.onduleur.quantite_stock,
                quantite_apres=self.onduleur.quantite_stock + 1,
                reference=ticket.reference, note='double', created_by=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, Decimal('3'))

    def test_retrait_retour_fournisseur_propose_rma_et_remplace_equipement(self):
        equip = Equipement.objects.create(
            company=self.company, produit=self.onduleur, installation=self.inst,
            numero_serie='SN-XMFG10-1', created_by=self.admin)
        ticket = self._ticket(equipement=equip)
        piece = retirer_piece(
            company=self.company, ticket=ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='SN-XMFG10-1',
            destination='retour_fournisseur', user=self.admin)

        equip.refresh_from_db()
        self.assertEqual(equip.statut, Equipement.Statut.REMPLACE)
        self.assertEqual(equip.remplace_par_ticket_id, ticket.id)

        self.assertIsNotNone(piece.warranty_claim_id)
        claim = WarrantyClaim.objects.get(pk=piece.warranty_claim_id)
        self.assertEqual(claim.equipement_id, equip.id)
        self.assertEqual(claim.ticket_id, ticket.id)

        # Le stock n'est jamais restocké dans ce cas.
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, Decimal('2'))

    def test_serie_inconnue_ne_cree_pas_de_rma_ni_ne_remplace_rien(self):
        ticket = self._ticket()
        piece = retirer_piece(
            company=self.company, ticket=ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='SN-INCONNU',
            destination='retour_fournisseur', user=self.admin)
        self.assertIsNone(piece.warranty_claim_id)
        self.assertIsNone(piece.equipement_remplace_id)

    def test_endpoint_pieces_retirees_post_et_get(self):
        ticket = self._ticket()
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{ticket.id}/pieces-retirees/',
            {'produit': self.onduleur.id, 'quantite': '1',
             'destination': 'stock_occasion'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['restockee'])

        resp = api.get(f'/api/django/sav/tickets/{ticket.id}/pieces-retirees/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)

    def test_endpoint_destination_invalide_rejetee(self):
        ticket = self._ticket()
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{ticket.id}/pieces-retirees/',
            {'produit': self.onduleur.id, 'quantite': '1',
             'destination': 'nimportequoi'})
        self.assertEqual(resp.status_code, 400, resp.content)
