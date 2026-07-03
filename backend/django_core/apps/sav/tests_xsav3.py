"""XSAV3 — Devis de réparation hors garantie depuis un ticket SAV.

Couvre :
  * création d'un devis brouillon lié au ticket (devis_id_ext posé) ;
  * pré-remplissage des lignes depuis les PieceConsommee, valorisées au prix
    de VENTE catalogue (jamais prix_achat) ;
  * garde : ticket sous garantie (constructeur calculée) → 400, aucun devis ;
  * cross-tenant : ticket d'une autre société → 404 ;
  * note automatique au chatter.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav3 -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.sav.models import Ticket, PieceConsommee
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='sav-xsav3', nom='Sav Co XSAV3'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV3CreerDevisTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav3-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV3', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur Y', sku='OND-Y-XSAV3',
            marque='Huawei', prix_achat=Decimal('500'),
            prix_vente=Decimal('900'), garantie_mois=24)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV3-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF,
            sous_garantie=Ticket.SousGarantie.NON,
            created_by=self.user)

    def test_creer_devis_hors_garantie(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/creer-devis/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        devis_id = resp.data['devis_id']
        devis = Devis.objects.get(pk=devis_id)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.client_id, self.client_obj.id)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.devis_id_ext, devis.id)
        # Note automatique au chatter.
        self.assertTrue(
            self.ticket.activites.filter(
                body__icontains=devis.reference).exists())

    def test_prefill_lignes_depuis_pieces_prix_vente(self):
        PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.produit,
            quantite=Decimal('2'), created_by=self.user)
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/creer-devis/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        devis = Devis.objects.get(pk=resp.data['devis_id'])
        lignes = list(devis.lignes.all())
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne.produit_id, self.produit.id)
        self.assertEqual(ligne.quantite, Decimal('2'))
        # Prix de VENTE catalogue — jamais prix_achat.
        self.assertEqual(ligne.prix_unitaire, self.produit.prix_vente)
        self.assertNotEqual(ligne.prix_unitaire, self.produit.prix_achat)

    def test_ticket_sous_garantie_bloque_creation(self):
        equip = None
        from apps.sav.models import Equipement
        equip = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst, date_pose=date.today() - timedelta(days=30),
            created_by=self.user)
        equip.recompute_garanties()
        equip.save()
        self.ticket.equipement = equip
        self.ticket.save(update_fields=['equipement'])
        self.assertEqual(
            self.ticket.sous_garantie_calcule, Ticket.SousGarantie.OUI)

        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/creer-devis/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.devis_id_ext)

    def test_cross_tenant_404(self):
        other = make_company(slug='sav-xsav3-other', nom='Other Co')
        other_user = User.objects.create_user(
            username='xsav3_other', password='x', role_legacy='admin',
            company=other)
        other_api = auth(other_user)
        resp = other_api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/creer-devis/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_aucun_prix_achat_expose_dans_reponse(self):
        PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.produit,
            quantite=Decimal('1'), created_by=self.user)
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/creer-devis/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # La réponse de l'action ne contient que devis_id/reference.
        self.assertNotIn('prix_achat', str(resp.data))
