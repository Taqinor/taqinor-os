"""PUB48 — Centre de notifications persistant (cloche console).

Prouve : une ``EngineAlert`` créée (``create_alert``/``emit_guarded_alert``,
sur envoi réel seulement) pousse une notification dans le moteur UNIFIÉ de
l'ERP (``notifications.Notification``, MÊME table que le reste de l'app —
jamais un second système) ; le snooze (``detail['snoozed_until']``, aucune
migration) masque une alerte de la liste ACTIVE jusqu'à échéance SANS jamais
la retirer de l'historique ; l'endpoint ``alertes/<id>/snooze/`` est
company-scopé + gated ``adsengine_manage`` ; ``deep_link_for_alert`` route
vers la bonne entité.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import alerts
from apps.adsengine.models import EngineAction, EngineAlert
from apps.notifications.models import Notification

User = get_user_model()
BASE = '/api/django/adsengine/alertes/'


def make_user(company, username, permissions, role_legacy='normal'):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NotifyAlertRecipientsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB48 Co', slug='pub48-co')

    def test_create_alert_notifies_admin_and_responsable(self):
        admin = make_user(
            self.company, 'pub48admin', ['adsengine_view'], role_legacy='admin')
        resp = make_user(
            self.company, 'pub48resp', ['adsengine_view'],
            role_legacy='responsable')
        normal = make_user(
            self.company, 'pub48normal', ['adsengine_view'],
            role_legacy='normal')

        alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.GARDE_FOU,
            message='Budget quotidien dépassé.')

        notifs = Notification.objects.filter(event_type='adsengine_alert')
        recipients = set(notifs.values_list('recipient_id', flat=True))
        self.assertIn(admin.id, recipients)
        self.assertIn(resp.id, recipients)
        self.assertNotIn(normal.id, recipients)
        self.assertTrue(all(
            n.title == 'Budget quotidien dépassé.' for n in notifs))

    def test_no_recipients_never_raises(self):
        # Aucun admin/responsable dans cette société : best-effort, pas de crash.
        alert = alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Sans destinataire.')
        self.assertIsNotNone(alert.pk)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notification_never_leaks_across_company(self):
        other = Company.objects.create(nom='PUB48 Other', slug='pub48-other')
        make_user(self.company, 'pub48admin2', ['adsengine_view'], role_legacy='admin')
        alerts.create_alert(
            other, alert_type=EngineAlert.Type.ANOMALIE, message='Autre société.')
        self.assertEqual(Notification.objects.count(), 0)


class SnoozeUnitTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SNZ Co', slug='snz-co')
        self.alert = EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Zéro résultat.')

    def test_not_snoozed_by_default(self):
        self.assertFalse(alerts.is_snoozed(self.alert))

    def test_snooze_then_is_snoozed_until_today_inclusive(self):
        today = timezone.now().date()
        future = (today + datetime.timedelta(days=3)).isoformat()
        alerts.snooze_alert(self.alert, future)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.detail['snoozed_until'], future)
        self.assertTrue(alerts.is_snoozed(self.alert, today=today.isoformat()))

    def test_snooze_expires_the_day_after(self):
        yesterday = (timezone.now().date() - datetime.timedelta(days=1)).isoformat()
        alerts.snooze_alert(self.alert, yesterday)
        self.alert.refresh_from_db()
        self.assertFalse(alerts.is_snoozed(self.alert))

    def test_unsnooze_clears_it(self):
        alerts.snooze_alert(self.alert, '2099-01-01')
        alerts.unsnooze_alert(self.alert)
        self.alert.refresh_from_db()
        self.assertNotIn('snoozed_until', self.alert.detail)
        self.assertFalse(alerts.is_snoozed(self.alert))


class AlertListSnoozeFilterApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='FLT Co', slug='flt-co')
        self.manager = make_user(
            self.company, 'fltmgr', ['adsengine_view', 'adsengine_manage'])
        self.active = alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Alerte active.')
        self.snoozed = alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Alerte reportée.')
        alerts.snooze_alert(self.snoozed, '2099-01-01')

    def test_list_hides_snoozed_alert(self):
        resp = auth(self.manager).get(BASE)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        ids = [r['id'] for r in results]
        self.assertIn(self.active.id, ids)
        self.assertNotIn(self.snoozed.id, ids)

    def test_history_still_shows_snoozed_alert(self):
        resp = auth(self.manager).get(BASE + 'history/')
        results = resp.data['results'] if 'results' in resp.data else resp.data
        ids = [r['id'] for r in results]
        self.assertIn(self.active.id, ids)
        self.assertIn(self.snoozed.id, ids)


class AlertSnoozeViewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SNZV Co', slug='snzv-co')
        self.manager = make_user(
            self.company, 'snzvmgr', ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(self.company, 'snzvviewer', ['adsengine_view'])
        self.alert = alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='À reporter.')

    def _url(self, alert_id):
        return f'{BASE}{alert_id}/snooze/'

    def test_snooze_success(self):
        resp = auth(self.manager).post(
            self._url(self.alert.id), {'until': '2099-06-01'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['snoozed_until'], '2099-06-01')
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.detail['snoozed_until'], '2099-06-01')

    def test_snooze_requires_until(self):
        resp = auth(self.manager).post(
            self._url(self.alert.id), {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_snooze_missing_alert_404(self):
        resp = auth(self.manager).post(
            self._url(999999), {'until': '2099-06-01'}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_view_only_cannot_snooze(self):
        resp = auth(self.viewer).post(
            self._url(self.alert.id), {'until': '2099-06-01'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_cannot_snooze_other_company_alert(self):
        other = Company.objects.create(nom='SNZV Other', slug='snzv-other')
        other_mgr = make_user(
            other, 'othermgr', ['adsengine_view', 'adsengine_manage'])
        resp = auth(other_mgr).post(
            self._url(self.alert.id), {'until': '2099-06-01'}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)


class DeepLinkForAlertTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DL Co', slug='dl-co')

    def test_links_to_approvals_when_action_linked(self):
        action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='Zéro résultat.')
        alert = EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Lié à une proposition.', action=action)
        self.assertIn('/publicite/approbations', alerts.deep_link_for_alert(alert))

    def test_links_to_template_screen_when_template_key_present(self):
        alert = EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.GARDE_FOU,
            message='Gabarit.',
            detail={'template_key': 'cost_per_signature_ceiling'})
        self.assertIn('/publicite/approbations', alerts.deep_link_for_alert(alert))

    def test_falls_back_to_regles_screen(self):
        alert = EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Sans action ni gabarit connu.')
        self.assertIn('/publicite/regles', alerts.deep_link_for_alert(alert))


class EmitGuardedAlertNotifyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EGN Co', slug='egn-co')
        self.admin = make_user(
            self.company, 'egnadmin', ['adsengine_view'], role_legacy='admin')

    def _emit(self, **kw):
        defaults = dict(
            template_key='frequency_runaway', target_type='adset',
            target_id='as1',
            context={'adset_name': 'as1', 'frequency': 3.6, 'ceiling': 3.0})
        defaults.update(kw)
        return alerts.emit_guarded_alert(self.company, **defaults)

    def test_fresh_send_notifies(self):
        self._emit()
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

    def test_dry_run_does_not_notify(self):
        self._emit(dry_run=True)
        self.assertEqual(Notification.objects.filter(recipient=self.admin).count(), 0)

    def test_cooldown_reoccurrence_does_not_renotify(self):
        self._emit()
        self._emit()  # rejoué dans le cooldown
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)
