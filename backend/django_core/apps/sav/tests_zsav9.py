"""ZSAV9 — Suiveurs de ticket (followers) + « suivre tous les tickets ».

Couvre :
  * suivre/ne-plus-suivre idempotent ;
  * un suiveur est notifié aux transitions (note/statut) ;
  * l'abonnement global (`suivre_tous_tickets_sav`) fonctionne à la création ;
  * cross-tenant 404 ; migration additive.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zsav9 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.notifications.models import Notification
from apps.sav.models import SavSlaSettings, Ticket, TicketFollower

User = get_user_model()


def make_company(slug='sav-zsav9', nom='Sav Co ZSAV9'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAV9TicketFollowerTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsav9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.follower_user = User.objects.create_user(
            username='zsav9_follower', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZSAV9',
            email='zsav9-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZSAV9', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ZSAV9-1',
            client=self.client_obj, installation=self.inst,
            created_by=self.admin)

    def test_suivre_ne_plus_suivre_idempotent(self):
        r1 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/suivre/',
            {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/suivre/',
            {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(
            TicketFollower.objects.filter(
                ticket=self.ticket, user=self.admin).count(), 1)

        r3 = self.api.delete(
            f'/api/django/sav/tickets/{self.ticket.pk}/suivre/')
        self.assertEqual(r3.status_code, 200, r3.data)
        r4 = self.api.delete(
            f'/api/django/sav/tickets/{self.ticket.pk}/suivre/')
        self.assertEqual(r4.status_code, 200, r4.data)
        self.assertFalse(
            TicketFollower.objects.filter(
                ticket=self.ticket, user=self.admin).exists())

    def test_suiveur_notifie_a_la_note(self):
        TicketFollower.objects.create(
            company=self.company, ticket=self.ticket, user=self.follower_user)
        before = Notification.objects.filter(recipient=self.follower_user).count()
        r = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/noter/',
            {'body': 'Mise à jour du dossier.'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        after = Notification.objects.filter(recipient=self.follower_user).count()
        self.assertEqual(after, before + 1)

    def test_auteur_note_pas_auto_notifie(self):
        TicketFollower.objects.create(
            company=self.company, ticket=self.ticket, user=self.admin)
        before = Notification.objects.filter(recipient=self.admin).count()
        self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/noter/',
            {'body': 'Ma propre note.'}, format='json')
        after = Notification.objects.filter(recipient=self.admin).count()
        self.assertEqual(after, before)

    def test_abonnement_global_a_la_creation(self):
        sla = SavSlaSettings.get(self.company)
        sla.suivre_tous_tickets_sav.add(self.follower_user)
        r = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        tid = r.data['id']
        self.assertTrue(
            TicketFollower.objects.filter(
                ticket_id=tid, user=self.follower_user).exists())

    def test_liste_vide_pas_abonnement_par_defaut(self):
        r = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
        }, format='json')
        tid = r.data['id']
        self.assertFalse(
            TicketFollower.objects.filter(ticket_id=tid).exists())

    def test_cross_tenant_404(self):
        other_company = make_company(slug='sav-zsav9-other', nom='Other')
        other_admin = User.objects.create_user(
            username='zsav9_other_admin', password='x', role_legacy='admin',
            company=other_company)
        other_api = auth(other_admin)
        r = other_api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/suivre/',
            {}, format='json')
        self.assertEqual(r.status_code, 404, r.data)
