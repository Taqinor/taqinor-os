"""Reporting — tableau de bord (dashboard) : agrégats lecture seule.

Couvre le bucketing du CA mensuel : 12 mois calendaires distincts finissant
ce mois (pas de dérive ni de saut/duplication de mois — bug i*30 jours).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.reporting.views import _ca_mensuel
from apps.ventes.models import Facture

User = get_user_model()


class TestCaMensuelBucketing(TestCase):
    """_ca_mensuel doit renvoyer 12 mois calendaires distincts, sans trou."""

    def test_twelve_distinct_calendar_months(self):
        series = _ca_mensuel(Facture.objects.none())
        self.assertEqual(len(series), 12)
        labels = [m['mois'] for m in series]
        # 12 libellés distincts (aucun mois dupliqué/sauté).
        self.assertEqual(len(set(labels)), 12)

    def test_last_bucket_is_current_month(self):
        series = _ca_mensuel(Facture.objects.none())
        mois_labels = {
            '01': 'Jan', '02': 'Fév', '03': 'Mar', '04': 'Avr',
            '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Aoû',
            '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Déc',
        }
        today = date.today()
        expected = f"{mois_labels[today.strftime('%m')]} {today.year}"
        self.assertEqual(series[-1]['mois'], expected)


class TestDashboardEndpoint(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='rep-views-co', defaults={'nom': 'Rep Views Co'})[0]
        self.user = User.objects.create_user(
            username='rep_views_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_dashboard_returns_twelve_months(self):
        resp = self.api.get('/api/django/reporting/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['ca_mensuel']), 12)

    def test_dashboard_xlsx_export(self):
        resp = self.api.get('/api/django/reporting/dashboard/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = (b''.join(resp.streaming_content)
                if getattr(resp, 'streaming', False) else resp.content)
        self.assertTrue(body.startswith(b'PK'))
