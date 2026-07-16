"""ENG13 — Tests des alertes moteur (EngineAlert + wa.me + wiring ENG9).

Prouve : ``create_alert`` persiste une alerte, une violation/anomalie ENG9 crée
réellement une ``EngineAlert`` (hook branché), le deep-link ``wa.me`` est bien
formé (avec/sans destinataire), et l'endpoint liste est company-scopé, GET-only
et gaté ``adsengine_view``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import alerts, guardrails
from apps.adsengine.models import (
    AdCampaignMirror, EngineAlert, GuardrailConfig, InsightSnapshot,
)

User = get_user_model()
BASE = '/api/django/adsengine/alertes/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class WaLinkTests(SimpleTestCase):
    def test_wa_link_without_recipient(self):
        link = alerts.wa_link('Coucou dépense')
        self.assertTrue(link.startswith('https://wa.me/?text='))
        self.assertIn('%20', link)  # espace encodé

    def test_wa_link_with_recipient(self):
        link = alerts.wa_link('Alerte', recipient='+212600000000')
        self.assertTrue(link.startswith('https://wa.me/212600000000?text='))


class CreateAlertTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AL Co', slug='al-co')

    def test_create_alert_persists_row(self):
        alert = alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.GARDE_FOU,
            message='Budget dépassé.')
        self.assertEqual(alert.company, self.company)
        self.assertEqual(EngineAlert.objects.count(), 1)


class Eng9WiringTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='W9 Co', slug='w9-co')
        self.config = GuardrailConfig.objects.create(
            company=self.company, anomaly_window_hours=48)
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='C', status='PAUSED')

    def test_anomaly_creates_alert_and_links_action(self):
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.camp.pk,
            date=datetime.date(2026, 7, 16), spend='40.00', results=0)
        created = guardrails.detect_anomalies(
            self.company, now=datetime.date(2026, 7, 16), config=self.config)
        self.assertEqual(len(created), 1)
        # Le hook ENG9 est branché : une EngineAlert anomalie existe et pointe
        # la proposition de pause.
        alert = EngineAlert.objects.get(alert_type=EngineAlert.Type.ANOMALIE)
        self.assertEqual(alert.action_id, created[0].id)

    def test_guardrail_violation_creates_alert(self):
        with self.assertRaises(guardrails.GuardrailViolation):
            guardrails.check_daily_ceiling(
                self.config, 500, company=self.company)
        self.assertTrue(EngineAlert.objects.filter(
            alert_type=EngineAlert.Type.GARDE_FOU).exists())


class AlertApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='API Al', slug='api-al')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.alert = alerts.create_alert(
            self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Dépense sans résultat.')

    def test_list_returns_alert_with_wa_links(self):
        resp = auth(self.viewer).get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['wa_links'][0].startswith('https://wa.me/'))

    def test_list_is_company_scoped(self):
        other = Company.objects.create(nom='Other', slug='other-al')
        alerts.create_alert(
            other, alert_type=EngineAlert.Type.ANOMALIE, message='autre')
        resp = auth(self.viewer).get(BASE)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)  # jamais l'alerte de l'autre société

    def test_create_is_not_allowed(self):
        # Les alertes sont créées par le moteur, jamais via l'API (GET-only).
        resp = auth(self.viewer).post(BASE, {
            'alert_type': 'anomalie', 'message': 'x'}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(auth(nobody).get(BASE).status_code, 403)
