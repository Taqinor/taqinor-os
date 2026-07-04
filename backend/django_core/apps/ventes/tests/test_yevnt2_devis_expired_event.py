"""Tests YEVNT2 — l'expiration automatique d'un devis (QJ5) émet
`devis_expired` sur le bus core exactement une fois, une notification part
au propriétaire (created_by), l'audit garde une trace (chatter), et une
réémission sur un devis déjà expiré est un no-op (le sweep ne le retraite
jamais deux fois — filtré en amont par le queryset ENVOYE)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import EventType, Notification
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.services import expire_stale_devis
from core.events import devis_expired

User = get_user_model()


def make_company(slug='yevnt2-co', nom='YEVNT2 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestDevisExpiredEvent(TestCase):
    def setUp(self):
        self.company = make_company()
        self.owner = User.objects.create_user(
            username='yevnt2_owner', password='x', role_legacy='commercial',
            company=self.company)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='E2',
            email='yevnt2@example.com', telephone='+212600000010')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-YEVNT2-0001',
            client=self.cl, statut=Devis.Statut.ENVOYE,
            date_validite=date.today() - timedelta(days=1),
            taux_tva=Decimal('20'), created_by=self.owner)

    def test_expire_emits_devis_expired_once(self):
        received = []

        def _listener(sender, devis, ancien_statut, **kwargs):
            received.append((devis.id, ancien_statut))
        devis_expired.connect(_listener, dispatch_uid='test_yevnt2_listener')
        try:
            expire_stale_devis()
        finally:
            devis_expired.disconnect(dispatch_uid='test_yevnt2_listener')
        self.assertEqual(received, [(self.devis.id, 'envoye')])

    def test_expire_notifies_owner(self):
        expire_stale_devis()
        notifs = Notification.objects.filter(
            recipient=self.owner, event_type=EventType.DEVIS_EXPIRED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(self.devis.reference, notifs.first().body)

    def test_expire_leaves_audit_chatter_trace(self):
        expire_stale_devis()
        acts = DevisActivity.objects.filter(devis=self.devis)
        self.assertTrue(
            acts.filter(body__icontains='expiré automatiquement').exists())

    def test_reemission_on_already_expired_devis_is_noop(self):
        expire_stale_devis()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.EXPIRE)
        notifs_before = Notification.objects.filter(
            recipient=self.owner, event_type=EventType.DEVIS_EXPIRED).count()
        # Second sweep pass: already-expired devis is outside the ENVOYE
        # queryset, so it is never revisited — no second event/notification.
        expire_stale_devis()
        notifs_after = Notification.objects.filter(
            recipient=self.owner, event_type=EventType.DEVIS_EXPIRED).count()
        self.assertEqual(notifs_before, notifs_after)
