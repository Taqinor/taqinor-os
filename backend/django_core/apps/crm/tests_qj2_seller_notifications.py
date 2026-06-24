"""QJ2 — Tests des notifications vendeur speed-to-lead.

Trois événements couverts :
  (a) arrivée d'un nouveau lead via le webhook site web → notify owner ;
  (b) première ouverture du lien public de proposition → notify owner ;
  (c) acceptation e-signature → notification in-app + wa.me au créateur du devis.

Chaque test vérifie :
  - La notification in-app est créée (via notifications.services.notify).
  - Le corps contient un lien wa.me quand le numéro est présent.
  - La société est correctement scopée (multi-tenant).
  - Un owner absent est un no-op (pas d'exception).
"""
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from django.contrib.auth import get_user_model

from apps.crm.models import Lead
from apps.crm.services import (
    notify_new_lead,
    notify_devis_opened,
)
from apps.notifications.models import EventType, Notification

User = get_user_model()


def _make_company(slug='co'):
    return Company.objects.create(nom=slug, slug=slug)


def _make_user(company, username='vendeur', role='responsable'):
    return User.objects.create_user(
        username=username, password='x',
        company=company, role_legacy=role)


def _make_lead(company, owner=None, telephone='0612345678', nom='Client Test'):
    return Lead.objects.create(
        company=company,
        nom=nom,
        telephone=telephone,
        owner=owner,
    )


# ── (a) notify_new_lead ───────────────────────────────────────────────────────

class NotifyNewLeadTests(TestCase):
    def setUp(self):
        self.company = _make_company('co-a')
        self.owner = _make_user(self.company, 'owner_a')

    def test_notification_created_for_owner(self):
        """Un nouveau lead déclenche une notification in-app pour le owner."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_new_lead(lead)
        notifs = Notification.objects.filter(recipient=self.owner)
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.event_type, EventType.LEAD_NEW)
        self.assertIn('Client Test', n.title)

    def test_body_contains_wa_url_when_phone_present(self):
        """Le corps de la notification contient un lien wa.me quand le numéro
        est présent (speed-to-lead : répondre en un tap)."""
        lead = _make_lead(self.company, owner=self.owner, telephone='0612345678')
        notify_new_lead(lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertIn('wa.me', n.body)

    def test_no_notification_without_owner(self):
        """Un lead sans owner ne lève pas d'exception et ne crée rien."""
        lead = _make_lead(self.company, owner=None)
        notify_new_lead(lead)  # must not raise
        self.assertEqual(Notification.objects.count(), 0)

    def test_company_scoped(self):
        """La notification est scopée à la société du lead (multi-tenant)."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_new_lead(lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.company, self.company)

    def test_no_phone_no_wa_url(self):
        """Sans numéro de téléphone, il n'y a pas de lien wa.me dans le corps."""
        lead = _make_lead(self.company, owner=self.owner, telephone='')
        notify_new_lead(lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertNotIn('wa.me', n.body)

    def test_notify_failure_never_propagates(self):
        """Une erreur dans notify() ne doit jamais remonter à l'appelant."""
        lead = _make_lead(self.company, owner=self.owner)
        with mock.patch('apps.notifications.services.notify',
                        side_effect=RuntimeError('boom')):
            try:
                notify_new_lead(lead)
            except Exception as exc:
                self.fail(f'notify_new_lead a levé une exception : {exc}')


# ── (b) notify_devis_opened ───────────────────────────────────────────────────

class NotifyDevisOpenedTests(TestCase):
    def setUp(self):
        self.company = _make_company('co-b')
        self.owner = _make_user(self.company, 'owner_b')

    def test_notification_created_on_first_open(self):
        """La première ouverture du devis déclenche une notification in-app."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_devis_opened('DEV-001', lead)
        notifs = Notification.objects.filter(recipient=self.owner)
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.event_type, EventType.DEVIS_OPENED)
        self.assertIn('DEV-001', n.title)

    def test_body_contains_wa_url(self):
        """Le corps contient un lien wa.me vers le prospect."""
        lead = _make_lead(self.company, owner=self.owner, telephone='0655555555')
        notify_devis_opened('DEV-002', lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertIn('wa.me', n.body)

    def test_no_owner_is_noop(self):
        """Sans owner le call est silent."""
        lead = _make_lead(self.company, owner=None)
        notify_devis_opened('DEV-003', lead)
        self.assertEqual(Notification.objects.count(), 0)

    def test_company_scoped(self):
        """La notification est scopée à la société du lead."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_devis_opened('DEV-004', lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertEqual(n.company, self.company)


# ── (c) acceptance — _notify_seller_accepted + wa.me ─────────────────────────

class NotifySellerAcceptedTests(TestCase):
    """Tests pour la notification vendeur à l'acceptation (QJ2 event c).

    La fonction interne ``_notify_seller_accepted`` est testée indirectement
    via ``apps.ventes.services`` pour rester dans les limites du cross-app
    boundary (pas d'import direct des modèles Ventes ici — on crée les objets
    via la DB pour éviter d'importer ventes.models dans les tests CRM).
    On utilise des mocks pour isoler la notification."""

    def setUp(self):
        self.company = _make_company('co-c')
        self.vendeur = _make_user(self.company, 'vendeur_c')

    def test_wa_url_built_from_lead_phone(self):
        """_build_acceptance_wa_url retourne un lien wa.me si le lead a un tel."""
        from apps.ventes.services import _build_acceptance_wa_url

        # Build minimal stub objects without hitting the DB.
        lead_stub = mock.Mock()
        lead_stub.whatsapp = None
        lead_stub.telephone = '0612345678'
        lead_stub.nom = 'Ali Benali'

        devis_stub = mock.Mock()
        devis_stub.lead = lead_stub
        devis_stub.client_id = None
        devis_stub.reference = 'DEV-TEST-01'

        url = _build_acceptance_wa_url(devis=devis_stub)
        self.assertIsNotNone(url)
        self.assertIn('wa.me', url)
        self.assertIn('212', url)  # normalized Moroccan number

    def test_wa_url_none_when_no_phone(self):
        """Sans numéro, _build_acceptance_wa_url renvoie None."""
        from apps.ventes.services import _build_acceptance_wa_url

        lead_stub = mock.Mock()
        lead_stub.whatsapp = ''
        lead_stub.telephone = ''
        lead_stub.nom = ''

        devis_stub = mock.Mock()
        devis_stub.lead = lead_stub
        devis_stub.client_id = None
        devis_stub.reference = 'DEV-X'

        url = _build_acceptance_wa_url(devis=devis_stub)
        self.assertIsNone(url)

    def test_notify_seller_accepted_creates_notification(self):
        """_notify_seller_accepted crée une notification in-app pour le vendeur."""
        from apps.ventes.services import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-99'
        devis_stub.pk = 1
        devis_stub.created_by = self.vendeur
        devis_stub.company = self.company
        devis_stub.client = None
        devis_stub.client_id = None
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=None)

        notifs = Notification.objects.filter(recipient=self.vendeur)
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.event_type, EventType.DEVIS_ACCEPTED)
        self.assertIn('DEV-99', n.title)

    def test_notify_seller_accepted_uses_correct_event_type(self):
        """La notification utilise le type 'devis_accepted' (EventType valide)."""
        from apps.ventes.services import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-EV'
        devis_stub.pk = 2
        devis_stub.created_by = self.vendeur
        devis_stub.company = self.company
        devis_stub.client = None
        devis_stub.client_id = None
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=None)

        n = Notification.objects.filter(recipient=self.vendeur).first()
        self.assertIsNotNone(n)
        self.assertIn(n.event_type, EventType.values)

    def test_self_notify_skipped(self):
        """Le créateur du devis n'est pas notifié quand il est l'acteur."""
        from apps.ventes.services import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-SELF'
        devis_stub.pk = 3
        devis_stub.created_by = self.vendeur
        devis_stub.company = self.company
        devis_stub.client = None
        devis_stub.client_id = None
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=self.vendeur)

        self.assertEqual(Notification.objects.count(), 0)

    def test_no_created_by_is_noop(self):
        """Pas de créateur = aucune notification, aucune exception."""
        from apps.ventes.services import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-NONE'
        devis_stub.pk = 4
        devis_stub.created_by = None
        devis_stub.company = self.company
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=None)
        self.assertEqual(Notification.objects.count(), 0)
