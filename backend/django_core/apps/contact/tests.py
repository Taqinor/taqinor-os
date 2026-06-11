"""Tests for the (parked) public contact form."""
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

VALID = {
    'nom': 'Test User',
    'email': 'test@example.com',
    'message': 'Bonjour, je suis intéressé.',
}


class TestContactParked(TestCase):
    def setUp(self):
        self.api = APIClient()

    @override_settings(CONTACT_FORM_ENABLED=False)
    def test_disabled_returns_404_and_sends_no_email(self):
        resp = self.api.post('/api/django/contact/', VALID)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(CONTACT_FORM_ENABLED=True)
    def test_enabled_accepts_and_sends_email(self):
        resp = self.api.post('/api/django/contact/', VALID)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('TAQINOR', mail.outbox[0].subject)
