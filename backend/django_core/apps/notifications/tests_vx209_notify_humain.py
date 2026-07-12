"""VX209 — `notify()` devient humain : heures calmes, bon event de mention,
purge, émetteurs manquants.

Couvre : (a) `notify()` respecte les heures calmes pour les canaux HORS-APP
sur un événement non-critique (l'in-app reste immédiate, et un événement
`'critique'` part toujours) ; (c) `purge_notifications_anciennes` supprime
les LUES > 60 j et archive les NON-LUES > 60 j ; (d) `SAV_ACTIVITE_DUE` et
`STOCK_EXPIRATION_SOON` sont désormais réellement émis, et warranty/
maintenance routent vers le technicien responsable quand il existe.

(b) — le fix `CHAT_MENTION` (au lieu de `LEAD_ASSIGNED`) est testé côté
appelant dans `apps/records/tests.py::test_mention_emits_chat_mention_event_type`
(c'est là que vit `_notify_mentions`)."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .models import EventType, Notification
from .services import notify

User = get_user_model()


def _make_company(name='VX209 Co'):
    return Company.objects.create(nom=name)


def _make_user(
        company, username='vx209_user', email='a@example.com',
        phone='+212600000000'):
    return User.objects.create_user(
        username=username, password='pw', email=email,
        company=company, phone_number=phone)


def _aware(y, m, d, hh, mm=0):
    # 2026-07-08 est un mercredi (jour ouvré par défaut, aucun férié configuré).
    return timezone.make_aware(datetime.datetime(y, m, d, hh, mm))


class NotifyQuietHoursTests(TestCase):
    """VX209(a)."""

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company)
        from .models import NotificationPreference
        NotificationPreference.objects.create(
            company=self.company, user=self.user,
            event_type=EventType.DIGEST, in_app=True, email=True,
            whatsapp=True)
        NotificationPreference.objects.create(
            company=self.company, user=self.user,
            event_type=EventType.INCIDENT_CRITICAL, in_app=True, email=True,
            whatsapp=True)

    def test_non_critical_at_23h_skips_offapp_channels_but_creates_inapp(self):
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_aware(2026, 7, 8, 23, 0)):
            with mock.patch(
                    'apps.notifications.services._dispatch_email') as email, \
                mock.patch(
                    'apps.notifications.services._dispatch_whatsapp') as wa:
                n = notify(self.user, EventType.DIGEST, 'Récap')
        self.assertIsNotNone(n)
        self.assertEqual(Notification.objects.count(), 1)
        email.assert_not_called()
        wa.assert_not_called()

    def test_non_critical_in_daytime_dispatches_offapp_channels(self):
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_aware(2026, 7, 8, 14, 0)):
            with mock.patch(
                    'apps.notifications.services._dispatch_email',
                    return_value=True) as email:
                notify(self.user, EventType.DIGEST, 'Récap')
        email.assert_called_once()

    def test_critical_event_at_23h_still_dispatches(self):
        # Un incident critique ne DOIT JAMAIS attendre le matin.
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_aware(2026, 7, 8, 23, 0)):
            with mock.patch(
                    'apps.notifications.services._dispatch_email',
                    return_value=True) as email:
                notify(self.user, EventType.INCIDENT_CRITICAL, 'Incident !')
        email.assert_called_once()

    def test_respect_quiet_hours_false_bypasses_gating(self):
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_aware(2026, 7, 8, 23, 0)):
            with mock.patch(
                    'apps.notifications.services._dispatch_email',
                    return_value=True) as email:
                notify(self.user, EventType.DIGEST, 'Récap',
                       respect_quiet_hours=False)
        email.assert_called_once()


class PurgeNotificationsAnciennesTests(TestCase):
    """VX209(c)."""

    def setUp(self):
        self.company = _make_company('Purge Co')
        self.user = _make_user(self.company, username='purge_user')

    def _create_at(self, *, read, days_old):
        n = Notification.objects.create(
            company=self.company, recipient=self.user,
            event_type=EventType.DIGEST, title='T', read=read)
        old = timezone.now() - datetime.timedelta(days=days_old)
        Notification.objects.filter(pk=n.pk).update(created_at=old)
        n.refresh_from_db()
        return n

    def test_read_older_than_60_days_is_deleted(self):
        from .sweeps import _sweep_purge_notifications
        old = self._create_at(read=True, days_old=61)
        _sweep_purge_notifications(self.company)
        self.assertFalse(Notification.objects.filter(pk=old.pk).exists())

    def test_unread_older_than_60_days_is_archived_not_deleted(self):
        from .sweeps import _sweep_purge_notifications
        old = self._create_at(read=False, days_old=61)
        _sweep_purge_notifications(self.company)
        old.refresh_from_db()
        self.assertTrue(old.archived)

    def test_recent_notifications_untouched(self):
        from .sweeps import _sweep_purge_notifications
        recent_read = self._create_at(read=True, days_old=10)
        recent_unread = self._create_at(read=False, days_old=10)
        _sweep_purge_notifications(self.company)
        self.assertTrue(
            Notification.objects.filter(pk=recent_read.pk).exists())
        recent_unread.refresh_from_db()
        self.assertFalse(recent_unread.archived)

    def test_purge_task_runs_across_companies(self):
        from .sweeps import purge_notifications_anciennes
        self._create_at(read=True, days_old=61)
        result = purge_notifications_anciennes()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)


class SweepSavActiviteDueTests(TestCase):
    """VX209(d) — `SAV_ACTIVITE_DUE` déclarée jamais émise."""

    def setUp(self):
        self.company = _make_company('SAV Activite Co')
        self.manager = User.objects.create_user(
            username='sav_act_mgr', password='pw',
            company=self.company, role_legacy='admin')

    def test_overdue_activite_notifies_assignee(self):
        from apps.crm.models import Client
        from apps.sav.models import Ticket, TicketActiviteAFaire
        from .sweeps import _sweep_sav_activite_due

        tech = User.objects.create_user(
            username='sav_act_tech', password='pw',
            company=self.company, role_legacy='technicien')
        client = Client.objects.create(company=self.company, nom='ClientTAF')
        ticket = Ticket.objects.create(
            company=self.company, client=client, reference='T-TAF-1',
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=datetime.date.today())
        TicketActiviteAFaire.objects.create(
            company=self.company, ticket=ticket, type='appel',
            titre='Rappeler le client',
            echeance=datetime.date.today() - datetime.timedelta(days=1),
            assigne=tech, fait=False)

        count = _sweep_sav_activite_due(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=tech,
                event_type=EventType.SAV_ACTIVITE_DUE).exists())
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.manager,
                event_type=EventType.SAV_ACTIVITE_DUE).exists())

    def test_unassigned_overdue_activite_notifies_managers(self):
        from apps.crm.models import Client
        from apps.sav.models import Ticket, TicketActiviteAFaire
        from .sweeps import _sweep_sav_activite_due

        client = Client.objects.create(company=self.company, nom='ClientTAF2')
        ticket = Ticket.objects.create(
            company=self.company, client=client, reference='T-TAF-2',
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=datetime.date.today())
        TicketActiviteAFaire.objects.create(
            company=self.company, ticket=ticket, type='visite',
            titre='Visite site',
            echeance=datetime.date.today() - datetime.timedelta(days=2),
            assigne=None, fait=False)

        count = _sweep_sav_activite_due(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.manager,
                event_type=EventType.SAV_ACTIVITE_DUE).exists())

    def test_done_activite_is_ignored(self):
        from apps.crm.models import Client
        from apps.sav.models import Ticket, TicketActiviteAFaire
        from .sweeps import _sweep_sav_activite_due

        client = Client.objects.create(company=self.company, nom='ClientTAF3')
        ticket = Ticket.objects.create(
            company=self.company, client=client, reference='T-TAF-3',
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=datetime.date.today())
        TicketActiviteAFaire.objects.create(
            company=self.company, ticket=ticket, type='email',
            titre='Déjà faite',
            echeance=datetime.date.today() - datetime.timedelta(days=1),
            fait=True, fait_le=timezone.now())

        count = _sweep_sav_activite_due(self.company)
        self.assertEqual(count, 0)


class SweepStockExpirationSoonTests(TestCase):
    """VX209(d) — `STOCK_EXPIRATION_SOON` déclarée jamais émise."""

    def setUp(self):
        self.company = _make_company('Stock Expi Co')
        self.manager = User.objects.create_user(
            username='stock_expi_mgr', password='pw',
            company=self.company, role_legacy='admin')

    def test_lot_expiring_soon_with_stock_emits(self):
        from apps.stock.models import LotEntrepot, Produit
        from .sweeps import _sweep_stock_expiration_soon

        produit = Produit.objects.create(
            company=self.company, nom='Batterie VX209', prix_vente=0)
        LotEntrepot.objects.create(
            company=self.company, produit=produit, numero_lot='LOT-1',
            date_peremption=datetime.date.today() + datetime.timedelta(days=10),
            quantite_recue=5, quantite_restante=3)

        count = _sweep_stock_expiration_soon(self.company)
        self.assertEqual(count, 1)
        n = Notification.objects.filter(
            recipient=self.manager,
            event_type=EventType.STOCK_EXPIRATION_SOON).first()
        self.assertIsNotNone(n)
        self.assertIn('LOT-1', n.body)

    def test_exhausted_lot_is_ignored(self):
        from apps.stock.models import LotEntrepot, Produit
        from .sweeps import _sweep_stock_expiration_soon

        produit = Produit.objects.create(
            company=self.company, nom='Batterie épuisée', prix_vente=0)
        LotEntrepot.objects.create(
            company=self.company, produit=produit, numero_lot='LOT-2',
            date_peremption=datetime.date.today() + datetime.timedelta(days=5),
            quantite_recue=5, quantite_restante=0)

        count = _sweep_stock_expiration_soon(self.company)
        self.assertEqual(count, 0)

    def test_far_future_lot_is_ignored(self):
        from apps.stock.models import LotEntrepot, Produit
        from .sweeps import _sweep_stock_expiration_soon

        produit = Produit.objects.create(
            company=self.company, nom='Batterie lointaine', prix_vente=0)
        LotEntrepot.objects.create(
            company=self.company, produit=produit, numero_lot='LOT-3',
            date_peremption=datetime.date.today() + datetime.timedelta(days=200),
            quantite_recue=5, quantite_restante=5)

        count = _sweep_stock_expiration_soon(self.company)
        self.assertEqual(count, 0)


class SweepOwnerFirstRoutingTests(TestCase):
    """VX209(d) — warranty/maintenance routent vers l'owner (technicien
    responsable du chantier) quand il existe, au lieu de toujours notifier
    tous les managers."""

    def setUp(self):
        self.company = _make_company('Owner First Co')
        self.manager = User.objects.create_user(
            username='ownerfirst_mgr', password='pw',
            company=self.company, role_legacy='admin')
        self.tech = User.objects.create_user(
            username='ownerfirst_tech', password='pw',
            company=self.company, role_legacy='technicien')

    def test_warranty_expiring_notifies_owner_when_present(self):
        from apps.crm.models import Client
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        from .sweeps import _sweep_warranty_expiring

        client = Client.objects.create(company=self.company, nom='ClientOwner')
        chantier = Installation.objects.create(
            company=self.company, client=client, reference='CH-OWNER-1',
            statut=Installation.Statut.CLOTURE,
            technicien_responsable=self.tech)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur Owner', prix_vente=0)
        Equipement.objects.create(
            company=self.company, produit=produit, installation=chantier,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie=datetime.date.today() + datetime.timedelta(days=30))

        count = _sweep_warranty_expiring(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.tech,
                event_type=EventType.WARRANTY_EXPIRING).exists())
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.manager,
                event_type=EventType.WARRANTY_EXPIRING).exists())
