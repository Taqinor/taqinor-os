"""ERR50 — le moteur de notifications est désormais câblé aux évènements métier.

Vérifie que les producteurs émettent bien une notification in-app :
- LEAD_ASSIGNED quand un Lead reçoit/réassigne un owner ;
- DEVIS_ACCEPTED quand un Devis passe au statut « accepté ».
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.notifications.models import EventType, Notification
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class TestNotificationProducers(TestCase):
    def setUp(self):
        self.company = Company.objects.create(slug='notif-sig-co', nom='Notif Sig Co')
        self.owner = User.objects.create_user(
            username='notif_owner', password='x', company=self.company)
        self.actor = User.objects.create_user(
            username='notif_actor', password='x', company=self.company)

    def test_lead_assignment_notifies_owner(self):
        Lead.objects.create(company=self.company, nom='Bennani', owner=self.owner)
        notifs = Notification.objects.filter(
            recipient=self.owner, event_type=EventType.LEAD_ASSIGNED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('Bennani', notifs.first().body)

    def test_lead_reassignment_notifies_new_owner_only(self):
        lead = Lead.objects.create(company=self.company, nom='X', owner=self.owner)
        Notification.objects.all().delete()
        lead.owner = self.actor
        lead.save()
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.actor, event_type=EventType.LEAD_ASSIGNED).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.owner, event_type=EventType.LEAD_ASSIGNED).count(), 0)

    def test_lead_save_without_owner_change_emits_nothing(self):
        lead = Lead.objects.create(company=self.company, nom='X', owner=self.owner)
        Notification.objects.all().delete()
        lead.nom = 'Y'
        lead.save()
        self.assertEqual(
            Notification.objects.filter(event_type=EventType.LEAD_ASSIGNED).count(), 0)

    def test_devis_accepted_notifies_creator(self):
        client = Client.objects.create(
            company=self.company, nom='ClientCo', email='c@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-NOTIF-1', client=client,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.actor)
        Notification.objects.all().delete()
        devis.statut = Devis.Statut.ACCEPTE
        devis.save()
        notifs = Notification.objects.filter(
            recipient=self.actor, event_type=EventType.DEVIS_ACCEPTED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('DEV-NOTIF-1', notifs.first().body)

    def test_devis_already_accepted_resave_emits_nothing(self):
        client = Client.objects.create(
            company=self.company, nom='ClientCo', email='c2@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-NOTIF-2', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.actor)
        Notification.objects.all().delete()
        devis.save()  # re-save while already accepted
        self.assertEqual(
            Notification.objects.filter(event_type=EventType.DEVIS_ACCEPTED).count(), 0)
