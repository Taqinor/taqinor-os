"""XSAV12 — Fusion de tickets doublons.

Couvre :
  * tout le contenu migré (activités, pièces consommées, checklist, PJ) ;
  * le doublon est conservé, marqué annulé avec motif « Doublon de {ref} » ;
  * cross-tenant → 404 ;
  * fusion d'un ticket sur lui-même refusée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav12 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.records.models import Attachment
from apps.stock.models import Produit
from apps.sav.models import (
    MaintenanceChecklistTemplate, PieceConsommee, Ticket, TicketChecklistItem,
)

User = get_user_model()


def make_company(slug='sav-xsav12', nom='Sav Co XSAV12'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV12FusionTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav12_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav12-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV12', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Pièce X', sku='PX-XSAV12',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'))
        self.principal = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV12-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.user)
        self.doublon = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV12-2',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.user)

        PieceConsommee.objects.create(
            company=self.company, ticket=self.doublon, produit=self.produit,
            quantite=Decimal('1'), created_by=self.user)
        tmpl = MaintenanceChecklistTemplate.objects.create(
            company=self.company, nom='Tpl XSAV12')
        TicketChecklistItem.objects.create(
            company=self.company, ticket=self.doublon, cle='c1',
            libelle='Étape 1', ordre=1)
        ct = ContentType.objects.get_for_model(Ticket)
        Attachment.objects.create(
            company=self.company, content_type=ct, object_id=self.doublon.pk,
            file_key='k1', filename='photo.jpg', uploaded_by=self.user)
        self._tmpl = tmpl

    def test_fusion_migre_tout_le_contenu(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': self.doublon.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        self.assertEqual(
            PieceConsommee.objects.filter(ticket=self.principal).count(), 1)
        self.assertEqual(
            TicketChecklistItem.objects.filter(ticket=self.principal).count(), 1)
        ct = ContentType.objects.get_for_model(Ticket)
        self.assertEqual(
            Attachment.objects.filter(
                content_type=ct, object_id=self.principal.pk).count(), 1)
        # Note croisée dans les deux chatters.
        self.assertTrue(
            self.principal.activites.filter(
                body__icontains=self.doublon.reference).exists())
        self.doublon.refresh_from_db()
        self.assertTrue(
            self.doublon.activites.filter(
                body__icontains=self.principal.reference).exists())

    def test_doublon_marque_annule_avec_motif(self):
        self.api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': self.doublon.pk}, format='json')
        self.doublon.refresh_from_db()
        self.assertTrue(self.doublon.annule)
        self.assertIn(self.principal.reference, self.doublon.motif_annulation)

    def test_fusion_sur_soi_meme_refusee(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': self.principal.pk}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_doublon_introuvable_404(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': 999999}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_404(self):
        other = make_company(slug='sav-xsav12-other', nom='Other Co')
        other_client = Client.objects.create(
            company=other, nom='O', prenom='C', email='o-xsav12@example.invalid')
        other_inst = Installation.objects.create(
            company=other, reference='CHT-XSAV12-O', client=other_client)
        other_ticket = Ticket.objects.create(
            company=other, reference='SAV-XSAV12-O1', client=other_client,
            installation=other_inst, type=Ticket.Type.CORRECTIF,
            created_by=self.user)

        # Le doublon appartient à une autre société : refusé.
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': other_ticket.pk}, format='json')
        self.assertEqual(resp.status_code, 404)

        # Le principal appartient à une autre société (vu par un user de
        # `self.company`) : la route elle-même 404 (get_object scopé société).
        other_user = User.objects.create_user(
            username='xsav12_other', password='x', role_legacy='admin',
            company=other)
        other_api = auth(other_user)
        resp2 = other_api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': self.doublon.pk}, format='json')
        self.assertEqual(resp2.status_code, 404)

    def test_doublon_conserve_en_lecture_seule(self):
        self.api.post(
            f'/api/django/sav/tickets/{self.principal.pk}/fusionner/',
            {'doublon_id': self.doublon.pk}, format='json')
        # Le doublon existe toujours (pas supprimé) — juste annulé.
        self.assertTrue(Ticket.objects.filter(pk=self.doublon.pk).exists())
