"""ASAV26 — « contrat de maintenance valide » = ``est_actif(date)`` partout
(SLA, avertissements de création, serializer) : un contrat échu hors grâce
n'impose plus son SLA.

Run :
    python manage.py test apps.sav.tests_asav26_contrat_valide -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance, SavSlaSettings, Ticket

User = get_user_model()
URL = '/api/django/sav/tickets/'


class ContratValideTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav26-co', defaults={'nom': 'ASAV26 Co'})
        self.admin = User.objects.create_user(
            username='asav26_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.save()
        self.today = timezone.localdate()

    def _client(self, prenom, *, debut_jours):
        client = Client.objects.create(
            company=self.company, nom='Client', prenom=prenom)
        ContratMaintenance.objects.create(
            company=self.company, client=client, actif=True,
            date_debut=self.today - timedelta(days=debut_jours),
            duree_mois=12, sla_resolution_days=1)
        return client

    def _creer(self, client):
        r = self.api.post(URL, {
            'client': client.pk, 'description': 'Panne ' + client.prenom,
            'priorite': 'normale'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return Ticket.objects.get(pk=r.data['id'])

    def test_echu_n_impose_pas_sla(self):
        client = self._client('echu', debut_jours=900)
        self.assertFalse(client.contrats_maintenance.first().est_actif())
        self.assertIsNone(ContratMaintenance.actif_pour_client(client))
        ticket = self._creer(client)
        self.assertEqual((ticket.sla_due_at - ticket.date_ouverture).days, 7)
        r = self.api.get(f'{URL}{ticket.pk}/')
        self.assertEqual(r.data['couverture_proposee'], 'facturable')

    def test_en_cours_impose_sla(self):
        client = self._client('encours', debut_jours=30)
        ticket = self._creer(client)
        self.assertEqual((ticket.sla_due_at - ticket.date_ouverture).days, 1)

    def _avertissement(self, client):
        from apps.sav.models import Equipement, TicketActivity
        from apps.stock.models import Produit
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'OND-{client.prenom}',
            prix_achat=0, prix_vente=100)
        couvert = Equipement.objects.create(
            company=self.company, produit=produit, numero_serie=f'A-{client.pk}')
        hors = Equipement.objects.create(
            company=self.company, produit=produit, numero_serie=f'B-{client.pk}')
        client.contrats_maintenance.first().equipements.add(couvert)
        r = self.api.post(URL, {
            'client': client.pk, 'equipement': hors.pk,
            'description': 'Panne ' + client.prenom,
            'priorite': 'normale'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return TicketActivity.objects.filter(
            ticket_id=r.data['id'],
            body__icontains='registre des équipements').exists()

    def test_avertissement_echu_absent(self):
        self.assertFalse(self._avertissement(
            self._client('warnechu', debut_jours=900)))
        self.assertTrue(self._avertissement(
            self._client('warnok', debut_jours=30)))
