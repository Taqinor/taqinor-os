"""ASAV40 — le client d'un ticket / d'une escalade d'alarme se déduit de
l'équipement aussi quand il a été vendu au comptoir (`client_vente`, sans
chantier).

Run :
    python manage.py test apps.sav.tests_asav40_client_vente -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import AlarmeOnduleur, Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


class ClientVenteTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav40-co', defaults={'nom': 'ASAV40 Co'})
        self.user = User.objects.create_user(
            username='asav40_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV40')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV40',
            prix_achat=0, prix_vente=100)
        self.comptoir = Equipement.objects.create(
            company=self.company, produit=produit, numero_serie='A40-C',
            client_vente=self.client_obj)
        self.orphelin = Equipement.objects.create(
            company=self.company, produit=produit, numero_serie='A40-O')

    def test_ticket_equipement_comptoir(self):
        r = self.api.post('/api/django/sav/tickets/', {
            'equipement': self.comptoir.pk, 'type': 'correctif',
            'description': 'Panne comptoir'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            Ticket.objects.get(pk=r.data['id']).client_id, self.client_obj.id)

    def test_escalade_equipement_comptoir(self):
        alarme = AlarmeOnduleur.objects.create(
            company=self.company, equipement=self.comptoir, code='E07')
        r = self.api.post(
            f'/api/django/sav/alarmes-onduleur/{alarme.pk}/escalader/',
            {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        alarme.refresh_from_db()
        self.assertEqual(alarme.statut, AlarmeOnduleur.Statut.ESCALADEE)
        self.assertEqual(alarme.ticket.client_id, self.client_obj.id)

    def test_sans_client_400(self):
        r = self.api.post('/api/django/sav/tickets/', {
            'equipement': self.orphelin.pk, 'type': 'correctif',
            'description': 'Panne'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('client', r.data)
