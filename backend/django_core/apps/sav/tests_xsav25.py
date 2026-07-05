"""XSAV25 — Catalogue de pièces compatibles par modèle d'équipement.

Couvre :
  * mapping CRUD company-scoped ;
  * le picker (`tickets/{id}/pieces-compatibles/`) renvoie les pièces
    compatibles du produit de l'équipement lié, y compris la chaîne de
    supersession (`remplace_par`) ;
  * migration additive, aucun ticket sans équipement ne casse (liste vide).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav25 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import CompatibilitePiece, Equipement, Ticket

User = get_user_model()


def make_company(slug='sav-xsav25', nom='Sav Co XSAV25'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV25CompatibilitePieceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav25_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav25-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV25', client=self.client_obj)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur Z', sku='OND-Z-XSAV25',
            prix_achat=300, prix_vente=600)
        self.fusible = Produit.objects.create(
            company=self.company, nom='Fusible 10A', sku='FUS-10A-XSAV25',
            prix_achat=5, prix_vente=15)
        self.carte = Produit.objects.create(
            company=self.company, nom='Carte contrôle', sku='CARTE-XSAV25',
            prix_achat=100, prix_vente=200)
        self.produit_sans_lien = Produit.objects.create(
            company=self.company, nom='Vis inox', sku='VIS-XSAV25',
            prix_achat=1, prix_vente=3)

    def test_mapping_crud_scoped(self):
        api = auth(self.admin)
        resp = api.post(
            '/api/django/sav/compatibilites-piece/',
            {'produit_equipement': self.onduleur.id, 'piece': self.fusible.id,
             'note': 'Fusible protection entrée'})
        self.assertEqual(resp.status_code, 201, resp.content)
        cp = CompatibilitePiece.objects.get(pk=resp.data['id'])
        self.assertEqual(cp.company_id, self.company.id)

    def test_picker_propose_compatibles_pour_equipement_lie(self):
        CompatibilitePiece.objects.create(
            company=self.company, produit_equipement=self.onduleur,
            piece=self.fusible, note='Protection entrée')
        CompatibilitePiece.objects.create(
            company=self.company, produit_equipement=self.onduleur,
            piece=self.carte)

        equip = Equipement.objects.create(
            company=self.company, produit=self.onduleur, installation=self.inst,
            created_by=self.admin)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV25-1',
            client=self.client_obj, installation=self.inst,
            equipement=equip, type=Ticket.Type.CORRECTIF,
            created_by=self.admin)

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ticket.id}/pieces-compatibles/')
        self.assertEqual(resp.status_code, 200, resp.content)
        piece_ids = {r['piece_id'] for r in resp.data['results']}
        self.assertEqual(piece_ids, {self.fusible.id, self.carte.id})
        self.assertNotIn(self.produit_sans_lien.id, piece_ids)

    def test_picker_vide_sans_equipement_lie(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV25-2',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ticket.id}/pieces-compatibles/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['results'], [])

    def test_chaine_de_supersession(self):
        fusible_ancien = Produit.objects.create(
            company=self.company, nom='Fusible 10A (ancien)',
            sku='FUS-10A-OLD-XSAV25', prix_achat=5, prix_vente=15)
        CompatibilitePiece.objects.create(
            company=self.company, produit_equipement=self.onduleur,
            piece=fusible_ancien, remplace_par=self.fusible,
            note='Discontinué par le fournisseur')

        equip = Equipement.objects.create(
            company=self.company, produit=self.onduleur, installation=self.inst,
            created_by=self.admin)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV25-3',
            client=self.client_obj, installation=self.inst,
            equipement=equip, type=Ticket.Type.CORRECTIF,
            created_by=self.admin)

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ticket.id}/pieces-compatibles/')
        piece_ids = {r['piece_id'] for r in resp.data['results']}
        # La pièce ancienne ET son remplacement apparaissent tous les deux.
        self.assertIn(fusible_ancien.id, piece_ids)
        self.assertIn(self.fusible.id, piece_ids)

    def test_cross_tenant_rejete(self):
        other_company = make_company(slug='sav-xsav25-other', nom='Autre Co')
        other_produit = Produit.objects.create(
            company=other_company, nom='Produit étranger',
            sku='PROD-OTHER-XSAV25', prix_achat=1, prix_vente=2)
        api = auth(self.admin)
        resp = api.post(
            '/api/django/sav/compatibilites-piece/',
            {'produit_equipement': self.onduleur.id, 'piece': other_produit.id})
        self.assertEqual(resp.status_code, 400, resp.content)
