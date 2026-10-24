"""ASAV2 — UNE décision « qui paie » (``services.decision_facturation``) pour
``generer-facture``, ``facturer`` et ``creer-devis``.

Run :
    python manage.py test apps.sav.tests_asav2_decision_facturation -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    TECHNICIEN_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS)
from apps.sav.models import ContratMaintenance, PieceConsommee, Ticket
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture

User = get_user_model()
BASE = '/api/django/sav/tickets'


class DecisionFacturationTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav2-co', defaults={'nom': 'ASAV2 Co'})
        self.user = User.objects.create_user(
            username='asav2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV2',
            email='asav2@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV2',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-VSPARC',
            prix_achat=Decimal('2000'), prix_vente=Decimal('5000'))
        self.today = timezone.localdate()

    def _ticket(self, ref, **kw):
        ticket = Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, type=Ticket.Type.CORRECTIF,
            created_by=self.user, date_ouverture=self.today, **kw)
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=self.produit,
            quantite=Decimal('1'), created_by=self.user)
        return ticket

    def _contrat(self):
        return ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True,
            date_debut=self.today - timedelta(days=30))

    def _prix_lignes(self, ticket):
        ticket.refresh_from_db()
        facture = Facture.objects.get(pk=ticket.facture_id_ext)
        return [ligne.prix_unitaire for ligne in facture.lignes.all()]

    def test_contrat_zero_deux_portes(self):
        self._contrat()
        for porte, ref in (('generer-facture', 'SAV-A2-1'),
                           ('facturer', 'SAV-A2-2')):
            ticket = self._ticket(ref)
            r = self.api.post(f'{BASE}/{ticket.pk}/{porte}/', {},
                              format='json')
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual(r.data['couverture'], 'contrat')
            self.assertEqual(self._prix_lignes(ticket), [Decimal('0')])

    def test_couverture_posee_zero_deux_portes(self):
        for porte, ref in (('generer-facture', 'SAV-A2-3'),
                           ('facturer', 'SAV-A2-4')):
            ticket = self._ticket(
                ref, couverture=Ticket.Couverture.GARANTIE)
            r = self.api.post(f'{BASE}/{ticket.pk}/{porte}/', {},
                              format='json')
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual(self._prix_lignes(ticket), [Decimal('0')])

    def test_recidive_403_deux_portes(self):
        for porte, ref in (('generer-facture', 'SAV-A2-5'),
                           ('facturer', 'SAV-A2-6'),
                           ('creer-devis', 'SAV-A2-7')):
            ticket = self._ticket(ref, non_facturable=True,
                                  est_recidive=True)
            r = self.api.post(f'{BASE}/{ticket.pk}/{porte}/', {},
                              format='json')
            self.assertEqual(r.status_code, 403, (porte, r.content))
            ticket.refresh_from_db()
            self.assertIsNone(ticket.facture_id_ext)
            self.assertIsNone(ticket.devis_id_ext)
        self.assertEqual(Facture.objects.filter(
            company=self.company).count(), 0)
        # Avec override responsable : la création est possible.
        ticket = self._ticket('SAV-A2-8', non_facturable=True,
                              est_recidive=True)
        r = self.api.post(f'{BASE}/{ticket.pk}/facturer/',
                          {'override': True}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._prix_lignes(ticket), [Decimal('5000')])

    def test_creer_devis_refuse_si_contrat(self):
        self._contrat()
        ticket = self._ticket('SAV-A2-9')
        r = self.api.post(f'{BASE}/{ticket.pk}/creer-devis/', {},
                          format='json')
        self.assertEqual(r.status_code, 409, r.content)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.devis_id_ext)
        self.assertEqual(Devis.objects.filter(
            company=self.company).count(), 0)

    def _api_role(self, username, nom, permissions):
        role = Role.objects.create(
            company=self.company, nom=nom, permissions=list(permissions))
        user = User.objects.create_user(
            username=username, password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return user, api

    def test_override_technicien_refuse_trois_portes(self):
        """ASAV104 — l'override d'une récidive non facturable est réservé au
        palier Administrateur/Responsable (``menu_tier``) : le rôle système
        Technicien porte ``sav_gerer`` mais reçoit 403 sur les trois portes."""
        tech, api_tech = self._api_role(
            'asav104_tech', 'Technicien', TECHNICIEN_PERMISSIONS)
        self.assertTrue(tech.is_responsable)
        for porte, ref in (('facturer', 'SAV-A104-1'),
                           ('generer-facture', 'SAV-A104-2'),
                           ('creer-devis', 'SAV-A104-3')):
            ticket = self._ticket(ref, non_facturable=True,
                                  est_recidive=True,
                                  technicien_responsable=tech)
            r = api_tech.post(f'{BASE}/{ticket.pk}/{porte}/',
                              {'override': True}, format='json')
            self.assertEqual(r.status_code, 403, (porte, r.content))
            self.assertIn('override responsable requis', r.data['detail'])
            ticket = Ticket.objects.get(pk=ticket.pk)
            self.assertIsNone(ticket.facture_id_ext)
            self.assertIsNone(ticket.devis_id_ext)
        self.assertEqual(Facture.objects.filter(
            client=self.client_obj).count(), 0)
        self.assertEqual(Devis.objects.filter(
            company=self.company).count(), 0)
        # Palier responsable : l'override passe, une facture à 5000.00.
        resp, api_resp = self._api_role(
            'asav104_resp', 'Technicien responsable',
            TECHNICIEN_RESP_PERMISSIONS)
        self.assertEqual(resp.menu_tier, 'responsable')
        ticket = self._ticket('SAV-A104-4', non_facturable=True,
                              est_recidive=True,
                              technicien_responsable=resp)
        r = api_resp.post(f'{BASE}/{ticket.pk}/facturer/',
                          {'override': True}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._prix_lignes(ticket), [Decimal('5000')])
        self.assertEqual(Facture.objects.filter(
            client=self.client_obj).count(), 1)
