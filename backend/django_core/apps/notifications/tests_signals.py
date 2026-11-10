"""ERR50 — le moteur de notifications est désormais câblé aux évènements métier.

Vérifie que les producteurs émettent bien une notification in-app :
- LEAD_ASSIGNED quand un Lead reçoit/réassigne un owner ;
- DEVIS_ACCEPTED quand un Devis passe au statut « accepté » ;
- SAV_TICKET_OPENED (YEVNT4) quand un ticket SAV est CRÉÉ.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
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

    def test_ntplt11_redis_coupe_a_l_acceptation_notif_livree_au_redemarrage(self):
        """NTPLT11 — l'envoi DEVIS_ACCEPTED est un effet durable de l'outbox :
        une panne pendant l'émission (Redis/cache coupé ⇒ ``notify`` lève)
        n'empêche pas l'acceptation et ne perd pas la notification — le
        worker la livre au redémarrage, UNE fois."""
        from datetime import timedelta
        from unittest import mock

        from django.utils import timezone

        from core import dispatch_outbox
        from core.models import OutboxEvent
        from apps.notifications import signals as notif_signals
        client = Client.objects.create(
            company=self.company, nom='ClientCo', email='c4@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-NTPLT11', client=client,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.actor)
        Notification.objects.all().delete()
        with mock.patch.object(notif_signals, 'notify',
                               side_effect=ConnectionError('Redis coupé')):
            devis.statut = Devis.Statut.ACCEPTE
            devis.save()
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        notifs = Notification.objects.filter(
            recipient=self.actor, event_type=EventType.DEVIS_ACCEPTED)
        self.assertEqual(notifs.count(), 0)
        ligne = OutboxEvent.objects.get(
            event_name=notif_signals.EFFET_DEVIS_ACCEPTE,
            company=self.company)
        self.assertEqual(ligne.statut, OutboxEvent.STATUT_FAILED)
        # Redémarrage : le worker rejoue — deux passages, une notification.
        plus_tard = timezone.now() + timedelta(hours=2)
        dispatch_outbox.dispatch_pending(now=plus_tard)
        dispatch_outbox.dispatch_pending(now=plus_tard)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('DEV-NTPLT11', notifs.first().body)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, OutboxEvent.STATUT_DELIVERED)

    def test_ntplt11_etape_crm_reste_synchrone_sur_devis_accepted(self):
        """NTPLT11 — l'invariant in-process (avancement d'étape crm) reste un
        récepteur SYNCHRONE du signal, jamais un effet d'outbox."""
        from core import events
        uids = {r[0][0] for r in events.devis_accepted.receivers}
        self.assertIn('crm_advance_stage_on_devis_accepted', uids)
        self.assertEqual(events.durable_handlers('devis_accepted'), [])

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

    def test_vnt53_avenant_accepte_ne_notifie_pas(self):
        client = Client.objects.create(
            company=self.company, nom='ClientCo', email='c3@example.com')
        v2 = Devis.objects.create(
            company=self.company, reference='DEV-NOTIF-3B', client=client,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.actor)
        Devis.objects.create(
            company=self.company, reference='DEV-NOTIF-3A', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.actor,
            is_active=False, superseded_by=v2)
        Notification.objects.all().delete()
        v2.statut = Devis.Statut.ACCEPTE
        v2.save()
        self.assertEqual(
            Notification.objects.filter(event_type=EventType.DEVIS_ACCEPTED).count(), 0)

    # ── YEVNT4 — SAV_TICKET_OPENED ───────────────────────────────────────────

    def test_sav_ticket_creation_notifies_assigned_technicien(self):
        from apps.sav.models import Ticket
        client = Client.objects.create(company=self.company, nom='SAV Client')
        Ticket.objects.create(
            company=self.company, client=client, reference='SAV-NOTIF-1',
            technicien_responsable=self.actor)
        notifs = Notification.objects.filter(
            recipient=self.actor, event_type=EventType.SAV_TICKET_OPENED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('SAV-NOTIF-1', notifs.first().body)

    def test_sav_ticket_creation_without_technicien_falls_back_to_managers(self):
        from apps.sav.models import Ticket
        self.owner.role_legacy = 'admin'
        self.owner.save(update_fields=['role_legacy'])
        client = Client.objects.create(company=self.company, nom='SAV Client 2')
        Ticket.objects.create(
            company=self.company, client=client, reference='SAV-NOTIF-2')
        self.assertTrue(Notification.objects.filter(
            recipient=self.owner, event_type=EventType.SAV_TICKET_OPENED).exists())

    def test_devis_expire_vendeur_inactif_va_au_responsable_actif(self):
        """ASOC1 (C-ASOC-001) — auteur inactif ⇒ le responsable actif du lead
        reçoit l'expiration ; jamais rien hors de l'app vers l'inactif ;
        `_notify_user_or_managers(inactif)` ⇒ les managers."""
        from unittest import mock

        from core.events import devis_expired
        from apps.notifications.services import notify
        from apps.notifications.sweeps import _notify_user_or_managers
        inactif = User.objects.create_user(
            username='notif_inactif', password='x', company=self.company,
            is_active=False)
        self.owner.role_legacy = 'admin'  # manager M
        self.owner.save(update_fields=['role_legacy'])
        lead = Lead.objects.create(
            company=self.company, nom='Lead ASOC1', owner=self.actor)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASOC1-1',
            client=Client.objects.create(company=self.company, nom='C1'),
            lead=lead, statut=Devis.Statut.EXPIRE, taux_tva=Decimal('20'),
            created_by=inactif)
        Notification.objects.all().delete()
        devis_expired.send(sender=Devis, devis=devis, ancien_statut='envoye')
        expire = Notification.objects.filter(event_type=EventType.DEVIS_EXPIRED)
        self.assertEqual(expire.filter(recipient=self.actor).count(), 1)
        self.assertEqual(expire.filter(recipient=inactif).count(), 0)
        # Sans responsable actif ⇒ les managers.
        lead.owner = None
        lead.save()
        Notification.objects.all().delete()
        devis_expired.send(sender=Devis, devis=devis, ancien_statut='envoye')
        self.assertEqual(list(expire.values_list('recipient', flat=True)),
                         [self.owner.pk])
        # notify(inactif) : in-app seul, aucun canal hors-app.
        with mock.patch('apps.notifications.services._diffuser_hors_app') \
                as diffuser, self.captureOnCommitCallbacks(execute=True):
            notify(inactif, EventType.DEVIS_EXPIRED, 'T', company=self.company,
                   respect_quiet_hours=False)
        self.assertEqual(set(diffuser.call_args.args[6]), {'in_app'})
        Notification.objects.all().delete()
        _notify_user_or_managers(
            inactif, self.company, EventType.DEVIS_EXPIRED, 'T', 'B')
        self.assertEqual(list(expire.values_list('recipient', flat=True)),
                         [self.owner.pk])

    def test_sav_ticket_update_does_not_reemit(self):
        from apps.sav.models import Ticket
        ticket = Ticket.objects.create(
            company=self.company, client=Client.objects.create(
                company=self.company, nom='SAV Client 3'),
            reference='SAV-NOTIF-3', technicien_responsable=self.actor)
        Notification.objects.all().delete()
        ticket.statut = Ticket.Statut.EN_COURS
        ticket.save()
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.SAV_TICKET_OPENED).count(), 0)
