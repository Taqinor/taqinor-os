"""Tests du moteur de notifications (N75)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company

from .models import EventType, Notification, NotificationPreference
from .services import merged_preferences, notify

User = get_user_model()


def _make_company(name='Acme'):
    return Company.objects.create(nom=name)


def _make_user(company, username='alice', email='', phone=''):
    return User.objects.create_user(
        username=username, password='pw', email=email,
        company=company, phone_number=phone or None)


class NotifyServiceTests(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company, email='alice@example.com')

    def test_in_app_created_by_default(self):
        n = notify(self.user, EventType.LEAD_ASSIGNED, 'Nouveau lead',
                   'Lead #4 vous est assigné', link='/crm/leads?lead=4')
        self.assertIsNotNone(n)
        self.assertEqual(n.recipient, self.user)
        self.assertEqual(n.company, self.company)
        self.assertEqual(n.event_type, EventType.LEAD_ASSIGNED)
        self.assertFalse(n.read)
        self.assertEqual(n.link, '/crm/leads?lead=4')
        self.assertEqual(Notification.objects.count(), 1)

    def test_in_app_disabled_creates_no_row(self):
        NotificationPreference.objects.create(
            company=self.company, user=self.user,
            event_type=EventType.LEAD_ASSIGNED, in_app=False)
        n = notify(self.user, EventType.LEAD_ASSIGNED, 'Titre')
        self.assertIsNone(n)
        self.assertEqual(Notification.objects.count(), 0)

    def test_unknown_event_type_is_ignored(self):
        n = notify(self.user, 'not_a_real_event', 'Titre')
        self.assertIsNone(n)
        self.assertEqual(Notification.objects.count(), 0)

    def test_none_user_is_safe(self):
        self.assertIsNone(notify(None, EventType.LEAD_ASSIGNED, 'Titre'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_email_channel_noop_when_unconfigured(self):
        # Canal email activé mais aucune configuration réelle → aucun envoi
        # réseau ; l'in-app est tout de même créée. Aucun crash.
        NotificationPreference.objects.create(
            company=self.company, user=self.user,
            event_type=EventType.DEVIS_ACCEPTED, in_app=True, email=True)
        with mock.patch(
                'apps.notifications.services._dispatch_email') as disp:
            # is_email_configured() renvoie False pour le backend console, donc
            # _dispatch_email part en no-op interne ; on vérifie surtout qu'aucune
            # exception ne remonte et que l'in-app existe.
            disp.return_value = False
            n = notify(self.user, EventType.DEVIS_ACCEPTED, 'Devis accepté')
        self.assertIsNotNone(n)
        self.assertEqual(Notification.objects.count(), 1)

    def test_dispatch_email_noop_without_address(self):
        from .services import _dispatch_email
        user = _make_user(self.company, username='noemail', email='')
        self.assertFalse(_dispatch_email(user, 'Titre', 'Corps'))

    def test_whatsapp_noop_without_phone(self):
        from .services import _dispatch_whatsapp
        user = _make_user(self.company, username='nophone', phone='')
        self.assertFalse(_dispatch_whatsapp(user, 'Titre', 'Corps'))

    def test_dispatch_best_effort_never_raises(self):
        # Même si une diffusion lève, notify ne propage jamais.
        NotificationPreference.objects.create(
            company=self.company, user=self.user,
            event_type=EventType.STOCK_LOW, in_app=True, email=True)
        with mock.patch(
                'apps.notifications.services._dispatch_email',
                side_effect=RuntimeError('boom')):
            n = notify(self.user, EventType.STOCK_LOW, 'Stock bas')
        self.assertIsNotNone(n)

    def test_in_app_body_is_bounded(self):
        # ERR91 — le corps in-app est borné comme le titre/lien, pas illimité.
        from .services import MAX_BODY_LEN
        huge = 'x' * (MAX_BODY_LEN + 500)
        n = notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body=huge)
        self.assertIsNotNone(n)
        self.assertEqual(len(n.body), MAX_BODY_LEN)
        n.refresh_from_db()
        self.assertEqual(len(n.body), MAX_BODY_LEN)

    def test_merged_preferences_covers_all_events(self):
        prefs = merged_preferences(self.user)
        self.assertEqual(len(prefs), len(EventType.choices))
        first = prefs[0]
        self.assertIn('event_type', first)
        self.assertIn('event_label', first)
        self.assertTrue(first['in_app'])  # défaut


class NotificationApiTests(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.alice = _make_user(self.company, username='alice')
        self.bob = _make_user(self.company, username='bob')
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def _notify_alice(self, **kw):
        return notify(self.alice, EventType.LEAD_ASSIGNED,
                      kw.get('title', 'T'), kw.get('body', ''))

    def test_list_only_my_notifications(self):
        self._notify_alice(title='A1')
        notify(self.bob, EventType.LEAD_ASSIGNED, 'B1')
        res = self.client.get('/api/django/notifications/notifications/')
        self.assertEqual(res.status_code, 200)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'A1')

    def test_unread_filter(self):
        n1 = self._notify_alice(title='unread')
        n2 = self._notify_alice(title='read')
        n2.read = True
        n2.save(update_fields=['read'])
        res = self.client.get(
            '/api/django/notifications/notifications/?unread=1')
        results = res.data['results'] if 'results' in res.data else res.data
        ids = {r['id'] for r in results}
        self.assertIn(n1.id, ids)
        self.assertNotIn(n2.id, ids)

    def test_unread_count(self):
        self._notify_alice()
        self._notify_alice()
        res = self.client.get(
            '/api/django/notifications/notifications/unread-count/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['unread'], 2)

    def test_mark_read(self):
        n = self._notify_alice()
        res = self.client.post(
            f'/api/django/notifications/notifications/{n.id}/read/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['read'])
        n.refresh_from_db()
        self.assertTrue(n.read)
        self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        self._notify_alice()
        self._notify_alice()
        res = self.client.post(
            '/api/django/notifications/notifications/read-all/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['updated'], 2)
        self.assertEqual(
            Notification.objects.filter(recipient=self.alice, read=False).count(), 0)

    def test_cannot_mark_others_notification(self):
        n = notify(self.bob, EventType.LEAD_ASSIGNED, 'B')
        res = self.client.post(
            f'/api/django/notifications/notifications/{n.id}/read/')
        self.assertEqual(res.status_code, 404)
        n.refresh_from_db()
        self.assertFalse(n.read)

    def test_preferences_list(self):
        res = self.client.get('/api/django/notifications/preferences/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), len(EventType.choices))

    def test_preferences_upsert(self):
        res = self.client.patch(
            f'/api/django/notifications/preferences/{EventType.FACTURE_OVERDUE}/',
            {'email': True, 'in_app': False}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email'])
        self.assertFalse(res.data['in_app'])
        pref = NotificationPreference.objects.get(
            user=self.alice, event_type=EventType.FACTURE_OVERDUE)
        self.assertTrue(pref.email)
        self.assertEqual(pref.company, self.company)

    def test_preferences_upsert_rejects_unknown_event(self):
        res = self.client.patch(
            '/api/django/notifications/preferences/bogus/',
            {'email': True}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_preferences_are_per_user(self):
        self.client.patch(
            f'/api/django/notifications/preferences/{EventType.STOCK_LOW}/',
            {'email': True}, format='json')
        # Bob garde les défauts (aucune ligne).
        self.assertFalse(
            NotificationPreference.objects.filter(user=self.bob).exists())


class DigestTaskTests(TestCase):
    """N76 — récapitulatifs quotidien & hebdomadaire par société."""

    def setUp(self):
        self.company = _make_company('DigestCo')
        # Destinataire « gérant » : on force le rôle legacy admin.
        self.manager = _make_user(self.company, username='manager')
        self.manager.role_legacy = 'admin'
        self.manager.save(update_fields=['role_legacy'])

    def _seed_data(self):
        """Sème un enregistrement par section pour vérifier le comptage."""
        from apps.crm.models import Client
        from apps.installations.models import Installation
        from apps.sav.models import ContratMaintenance, Ticket
        from apps.ventes.models import Devis, Facture

        client = Client.objects.create(company=self.company, nom='Client X')
        # Chantier à planifier (signé).
        Installation.objects.create(
            company=self.company, client=client, reference='CH-1',
            statut=Installation.Statut.SIGNE)
        # Devis envoyé (en attente d'acceptation).
        Devis.objects.create(
            company=self.company, client=client, reference='DV-1',
            statut=Devis.Statut.ENVOYE)
        # Facture en retard.
        Facture.objects.create(
            company=self.company, client=client, reference='FA-1',
            statut=Facture.Statut.EN_RETARD)
        # SAV ouvert.
        Ticket.objects.create(
            company=self.company, client=client, reference='SAV-1',
            statut=Ticket.Statut.NOUVEAU)
        # Maintenance due (date de début dans le passé, contrat actif).
        from datetime import date, timedelta
        ContratMaintenance.objects.create(
            company=self.company, client=client,
            date_debut=date.today() - timedelta(days=400), actif=True)

    def test_daily_digest_produces_notification_with_seeded_data(self):
        from .digests import daily_digest
        self._seed_data()
        emitted = daily_digest()
        self.assertGreaterEqual(emitted, 1)
        notif = Notification.objects.filter(
            recipient=self.manager, event_type=EventType.DIGEST).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.company, self.company)
        self.assertIn('quotidien', notif.title.lower())
        # Le corps liste chaque section ; chaque section sème 1 → compte 1.
        self.assertIn('Chantiers à planifier : 1', notif.body)
        self.assertIn('Devis en attente', notif.body)
        self.assertIn('Paiements en retard : 1', notif.body)
        self.assertIn('SAV ouverts : 1', notif.body)
        self.assertIn('Maintenances dues : 1', notif.body)

    def test_weekly_digest_produces_notification(self):
        from .digests import weekly_digest
        self._seed_data()
        emitted = weekly_digest()
        self.assertGreaterEqual(emitted, 1)
        notif = Notification.objects.filter(
            recipient=self.manager, event_type=EventType.DIGEST).first()
        self.assertIsNotNone(notif)
        self.assertIn('hebdomadaire', notif.title.lower())

    def test_digest_scoped_per_company(self):
        """Un manager ne reçoit QUE le résumé de SA société."""
        from .digests import daily_digest
        other = _make_company('AutreCo')
        other_mgr = _make_user(other, username='othermgr')
        other_mgr.role_legacy = 'admin'
        other_mgr.save(update_fields=['role_legacy'])
        self._seed_data()  # données uniquement dans self.company
        daily_digest()
        # L'autre société n'a aucune donnée : son résumé est tout à zéro.
        other_notif = Notification.objects.filter(
            recipient=other_mgr, event_type=EventType.DIGEST).first()
        self.assertIsNotNone(other_notif)
        self.assertIn('Chantiers à planifier : 0', other_notif.body)
        self.assertNotIn('Chantiers à planifier : 1', other_notif.body)

    def test_digest_noop_without_recipients(self):
        """Société sans utilisateur → aucune notification, aucune erreur."""
        from .digests import daily_digest
        empty = _make_company('VideCo')  # noqa: F841 - société sans user
        emitted = daily_digest()
        # Aucune notification pour la société vide ; pas de crash.
        self.assertEqual(
            Notification.objects.filter(company=empty).count(), 0)
        self.assertIsInstance(emitted, int)


class WebPushTests(TestCase):
    """N92 — Web push (PWA) : abonnement par appareil + no-op sans clés VAPID."""

    def setUp(self):
        from .models import PushSubscription  # noqa: F401 - import vérifie le modèle
        self.company = _make_company('PushCo')
        self.user = _make_user(self.company, username='pushuser')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_subscribe_stores_company_scoped_subscription(self):
        from .models import PushSubscription
        res = self.client.post(
            '/api/django/notifications/push/subscribe/',
            {'endpoint': 'https://push.example/abc',
             'keys': {'p256dh': 'KEYp256', 'auth': 'KEYauth'}},
            format='json')
        self.assertEqual(res.status_code, 201, res.data)
        sub = PushSubscription.objects.get(endpoint='https://push.example/abc')
        # company + user posés CÔTÉ SERVEUR (jamais lus du corps).
        self.assertEqual(sub.company, self.company)
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.p256dh, 'KEYp256')
        self.assertEqual(sub.auth, 'KEYauth')

    def test_subscribe_is_idempotent_by_endpoint(self):
        from .models import PushSubscription
        body = {'endpoint': 'https://push.example/dup',
                'keys': {'p256dh': 'A', 'auth': 'B'}}
        self.client.post(
            '/api/django/notifications/push/subscribe/', body, format='json')
        body['keys'] = {'p256dh': 'A2', 'auth': 'B2'}
        self.client.post(
            '/api/django/notifications/push/subscribe/', body, format='json')
        subs = PushSubscription.objects.filter(endpoint='https://push.example/dup')
        self.assertEqual(subs.count(), 1)
        self.assertEqual(subs.first().p256dh, 'A2')

    def test_subscribe_rejects_incomplete(self):
        res = self.client.post(
            '/api/django/notifications/push/subscribe/',
            {'endpoint': 'https://push.example/x'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_unsubscribe_only_own_subscription(self):
        from .models import PushSubscription
        other = _make_user(self.company, username='other')
        PushSubscription.objects.create(
            company=self.company, user=other,
            endpoint='https://push.example/other', p256dh='p', auth='a')
        res = self.client.post(
            '/api/django/notifications/push/unsubscribe/',
            {'endpoint': 'https://push.example/other'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['deleted'], 0)  # pas le mien → rien supprimé
        self.assertTrue(PushSubscription.objects.filter(
            endpoint='https://push.example/other').exists())

    @override_settings(VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='')
    def test_vapid_public_key_empty_when_unconfigured(self):
        res = self.client.get(
            '/api/django/notifications/push/vapid-public-key/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['public_key'], '')

    @override_settings(VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='')
    def test_notify_no_vapid_keys_does_not_error(self):
        from .models import PushSubscription
        # Même avec un abonnement présent, sans clés VAPID le push est un NO-OP
        # total : notify() ne lève jamais et l'in-app est créée normalement.
        PushSubscription.objects.create(
            company=self.company, user=self.user,
            endpoint='https://push.example/me', p256dh='p', auth='a')
        n = notify(self.user, EventType.LEAD_ASSIGNED, 'Test push')
        self.assertIsNotNone(n)
        self.assertEqual(Notification.objects.count(), 1)

    @override_settings(
        VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv',
        VAPID_ADMIN_EMAIL='admin@x.com')
    def test_dispatch_webpush_noop_without_subscriptions(self):
        # Clés présentes mais aucun abonnement → 0 envoi, aucune erreur.
        from .services import _dispatch_webpush
        self.assertEqual(
            _dispatch_webpush(self.user, 'Titre', 'Corps'), 0)
