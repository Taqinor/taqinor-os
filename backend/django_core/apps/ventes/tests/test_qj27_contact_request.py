"""QJ27 — « Être contacté » côté client : endpoint public tokenisé qui notifie
le RESPONSABLE du lead ET son SUPÉRIEUR (repli managers société).

Couvre :
  * les DEUX destinataires (owner + owner.supervisor) reçoivent la notification ;
  * repli quand le supérieur manque → managers « Commercial responsable » /
    « Directeur » de la société ;
  * repli quand le owner manque ;
  * isolation multi-société (un manager d'une AUTRE société n'est jamais notifié) ;
  * note chatter SYSTÈME sur le lead (user=None — ne fait pas avancer QJ7) ;
  * idempotence (double POST → une seule vague de notifications) ;
  * jeton invalide/expiré → 404 sans fuite ;
  * QJ2 étendu : notify_new_lead / notify_devis_opened touchent aussi le supérieur.
"""
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.services import (
    lead_notification_recipients,
    notify_devis_opened,
    notify_new_lead,
)
from apps.notifications.models import EventType, Notification
from apps.roles.models import Role
from apps.ventes.models import Devis, ShareLink

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, supervisor=None, role=None):
    return User.objects.create_user(
        username=username, password='x', company=company,
        supervisor=supervisor, role=role, role_legacy='responsable')


class ContactRequestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.company = _company('qj27-co')
        self.boss = _user(self.company, 'qj27-boss')
        self.owner = _user(self.company, 'qj27-owner', supervisor=self.boss)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678',
            owner=self.owner)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJ27-0001',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.BROUILLON, created_by=self.owner)
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _post(self, token=None, body=None):
        token = token or self.link.token
        return self.api.post(
            f'/api/django/public/proposal/{token}/contact/',
            body or {}, format='json')


class ContactRequestRecipientsTests(ContactRequestBase):
    def test_notifies_owner_and_supervisor(self):
        resp = self._post(body={'canal': 'rappel', 'message': 'Le matin svp'})
        self.assertEqual(resp.status_code, 200)
        notifs = Notification.objects.filter(
            event_type=EventType.CLIENT_CONTACT_REQUEST)
        self.assertEqual(
            set(notifs.values_list('recipient_id', flat=True)),
            {self.owner.pk, self.boss.pk})
        n = notifs.filter(recipient=self.owner).first()
        self.assertIn('DEV-QJ27-0001', n.title)
        self.assertIn('Le matin svp', n.body)

    def test_fallback_to_company_managers_without_supervisor(self):
        self.owner.supervisor = None
        self.owner.save(update_fields=['supervisor'])
        role = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=['crm_voir'])
        manager = _user(self.company, 'qj27-manager', role=role)
        self._post()
        recipients = set(Notification.objects.filter(
            event_type=EventType.CLIENT_CONTACT_REQUEST,
        ).values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.owner.pk, manager.pk})

    def test_fallback_to_company_managers_without_owner(self):
        self.lead.owner = None
        self.lead.save(update_fields=['owner'])
        role = Role.objects.create(
            company=self.company, nom='Directeur', permissions=['crm_voir'])
        directeur = _user(self.company, 'qj27-directeur', role=role)
        self._post()
        recipients = set(Notification.objects.filter(
            event_type=EventType.CLIENT_CONTACT_REQUEST,
        ).values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {directeur.pk})

    def test_company_scoped_never_notifies_other_company(self):
        other = _company('qj27-autre')
        role = Role.objects.create(
            company=other, nom='Directeur', permissions=['crm_voir'])
        etranger = _user(other, 'qj27-etranger', role=role)
        self.owner.supervisor = None
        self.owner.save(update_fields=['supervisor'])
        self._post()
        self.assertFalse(Notification.objects.filter(
            recipient=etranger).exists())
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.company, self.company)


class ContactRequestBehaviourTests(ContactRequestBase):
    def test_chatter_note_is_system_and_logged(self):
        self._post(body={'canal': 'whatsapp'})
        act = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__contains='demande à être contacté').first()
        self.assertIsNotNone(act)
        self.assertIsNone(act.user)  # note SYSTÈME — QJ7 ne bouge pas
        self.assertEqual(act.company, self.company)

    def test_idempotent_double_post_notifies_once(self):
        r1 = self._post()
        r2 = self._post()
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r1.data['already_sent'])
        self.assertTrue(r2.data['already_sent'])
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.CLIENT_CONTACT_REQUEST,
                recipient=self.owner).count(),
            1)

    def _contact_notif_count(self):
        # Le endpoint 404 sur jeton invalide/expiré AVANT toute notification :
        # on vérifie qu'aucune notification de demande-de-contact n'est créée
        # (le setUp peut produire d'autres notifications CRM de fond).
        return Notification.objects.filter(
            event_type=EventType.CLIENT_CONTACT_REQUEST).count()

    def test_invalid_token_404(self):
        resp = self._post(token='pas-un-jeton-valide')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._contact_notif_count(), 0)

    def test_expired_token_404(self):
        self.link.expires_at = timezone.now()
        self.link.save(update_fields=['expires_at'])
        resp = self._post()
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._contact_notif_count(), 0)


class QJ2SupervisorExtensionTests(TestCase):
    """QJ27 — les notifications QJ2 (nouveau lead / première ouverture)
    atteignent AUSSI le supérieur du responsable."""

    def setUp(self):
        cache.clear()
        self.company = _company('qj27-qj2')
        self.boss = _user(self.company, 'qj2-boss')
        self.owner = _user(self.company, 'qj2-owner', supervisor=self.boss)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678',
            owner=self.owner)

    def test_recipients_helper_owner_plus_supervisor(self):
        recipients = lead_notification_recipients(self.lead)
        self.assertEqual([u.pk for u in recipients],
                         [self.owner.pk, self.boss.pk])

    def test_new_lead_notifies_supervisor_too(self):
        notify_new_lead(self.lead)
        recipients = set(Notification.objects.filter(
            event_type=EventType.LEAD_NEW,
        ).values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.owner.pk, self.boss.pk})

    def test_devis_opened_notifies_supervisor_too(self):
        notify_devis_opened('DEV-QJ2-0001', self.lead)
        recipients = set(Notification.objects.filter(
            event_type=EventType.DEVIS_OPENED,
        ).values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.owner.pk, self.boss.pk})

    def test_owner_without_supervisor_falls_back_to_managers(self):
        self.owner.supervisor = None
        self.owner.save(update_fields=['supervisor'])
        role = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=['crm_voir'])
        manager = _user(self.company, 'qj2-manager', role=role)
        notify_new_lead(self.lead)
        recipients = set(Notification.objects.filter(
            event_type=EventType.LEAD_NEW,
        ).values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.owner.pk, manager.pk})
