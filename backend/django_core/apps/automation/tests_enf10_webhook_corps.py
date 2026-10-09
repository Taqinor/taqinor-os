"""ENF10 — création de webhook entrant : corps invalide => 400, jamais 500."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

BASE = '/api/django/automation/incoming-webhooks/'


class WebhookCorpsInvalideTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='enf10-co', defaults={'nom': 'ENF10'})
        admin = get_user_model().objects.create_user(
            username='enf10-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(admin)

    def test_rule_objet_400(self):
        res = self.api.post(BASE, {'rule': {}}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_rule_absente_400(self):
        res = self.api.post(BASE, {}, format='json')
        self.assertEqual(res.status_code, 400)
