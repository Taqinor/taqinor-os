"""VX212 — transparence « pourquoi je reçois ça » + contexte décisionnel.

(a) une notification porte une raison COURTE fermée (`Notification.reason`),
    posée à un sous-ensemble représentatif des sites d'émission ; (b) l'email/
    corps de la demande d'approbation (DemandeAchat, VX99) embarque désormais
    le montant estimé + l'objet (contexte décisionnel), jamais un bouton
    « Approuver » par lien (aucune mutation non-authentifiée n'est introduite
    ici — on ne touche qu'au CORPS du message).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import EventType, Notification, NotificationReason

User = get_user_model()


def _make_company(name='VX212 Co'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class NotifyReasonTests(TestCase):
    """`notify(reason=...)` — persistée si valide, ignorée sinon (jamais une
    exception, jamais un 500)."""

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company, 'vx212_user')

    def test_valid_reason_is_persisted(self):
        from .services import notify
        n = notify(
            self.user, EventType.LEAD_ASSIGNED, 'Titre', body='corps',
            reason=NotificationReason.MANAGER)
        self.assertEqual(n.reason, NotificationReason.MANAGER)

    def test_unknown_reason_is_silently_ignored(self):
        from .services import notify
        n = notify(
            self.user, EventType.LEAD_ASSIGNED, 'Titre', body='corps',
            reason='invented_reason')
        self.assertEqual(n.reason, '')

    def test_default_reason_is_empty(self):
        from .services import notify
        n = notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='corps')
        self.assertEqual(n.reason, '')

    def test_serializer_exposes_reason_label(self):
        from .services import notify
        notify(
            self.user, EventType.LEAD_ASSIGNED, 'Titre', body='corps',
            reason=NotificationReason.ASSIGNE)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get('/api/django/notifications/notifications/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        item = results[0]
        self.assertEqual(item['reason'], 'assigne_a_vous')
        self.assertEqual(item['reason_label'], 'Assigné à vous')


class LeadAssignedReasonTests(TestCase):
    """Producteur `LEAD_ASSIGNED` (signals.py) → reason='assigne_a_vous'."""

    def test_lead_assignment_carries_reason(self):
        from apps.crm.models import Lead
        company = _make_company('VX212 Lead Co')
        owner = _make_user(company, 'vx212_owner')
        Lead.objects.create(company=company, nom='Lead VX212', owner=owner)
        notif = Notification.objects.filter(
            recipient=owner, event_type=EventType.LEAD_ASSIGNED,
            company=company).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.reason, NotificationReason.ASSIGNE)


class ManagerApprovalReasonTests(TestCase):
    """Les 3 boucles `_managers(company)` (automation/compta/installations)
    posent reason='manager' — installations en plus embarque montant+objet
    dans le corps (VX212(b))."""

    def setUp(self):
        self.company = _make_company('VX212 DA Co')
        self.approver = _make_user(self.company, 'vx212_approver', role_legacy='admin')
        self.requester = _make_user(self.company, 'vx212_requester')

    def test_demande_achat_submission_carries_reason_and_context(self):
        from apps.installations.models import DemandeAchat
        from apps.installations.models_demande_achat import DemandeAchatLigne

        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-VX212-1', objet='Onduleurs solaires',
            created_by=self.requester)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Onduleur 5kW', quantite=2, prix_estime=3000)
        Notification.objects.all().delete()

        da.statut = DemandeAchat.Statut.SOUMISE
        da.save()

        notif = Notification.objects.filter(
            recipient=self.approver, event_type=EventType.APPROVAL_REQUESTED
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.reason, NotificationReason.MANAGER)
        # VX212(b) — le corps (email ET in-app, même pipeline `notify()`)
        # embarque le montant estimé + l'objet — contexte décisionnel,
        # jamais un bouton « Approuver » par lien email.
        self.assertIn('6000', notif.body)
        self.assertIn('Onduleurs solaires', notif.body)


class ResolveRecipientsReasonTests(TestCase):
    """`resolve_recipients_reason` : 'regle_de_routage' si une règle active
    existe, sinon 'manager' (repli historique)."""

    def setUp(self):
        self.company = _make_company('VX212 Routing Co')

    def test_no_rule_falls_back_to_manager(self):
        from .services import resolve_recipients_reason
        reason = resolve_recipients_reason(self.company, EventType.BON_COMMANDE_CREE)
        self.assertEqual(reason, NotificationReason.MANAGER)

    def test_active_rule_gives_routing_reason(self):
        from .models import NotificationRoutingRule
        from .services import resolve_recipients_reason
        NotificationRoutingRule.objects.create(
            company=self.company, event_type=EventType.BON_COMMANDE_CREE,
            target_role='admin', enabled=True)
        reason = resolve_recipients_reason(self.company, EventType.BON_COMMANDE_CREE)
        self.assertEqual(reason, NotificationReason.ROUTING_RULE)


class FollowerReasonTests(TestCase):
    """`notify_followers` (records/services.py) → reason='vous_suivez'."""

    def test_follower_notified_with_reason(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.crm.models import Lead
        from apps.records.services import follow, notify_followers

        company = _make_company('VX212 Follow Co')
        follower = _make_user(company, 'vx212_follower')
        lead = Lead.objects.create(company=company, nom='Lead suivi')
        ct = ContentType.objects.get_for_model(Lead)
        follow(company=company, content_type=ct, object_id=lead.id, user=follower)

        notify_followers(
            content_type=ct, object_id=lead.id, title='Nouvelle note',
            body='Un commentaire', link=f'/crm/leads?lead={lead.id}')

        notif = Notification.objects.filter(recipient=follower).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.reason, NotificationReason.FOLLOWING)
