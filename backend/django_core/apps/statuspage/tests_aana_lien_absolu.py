"""AANA43 — le lien de confirmation d'abonnement est ABSOLU.

Un e-mail ne peut pas porter un chemin relatif : le lien n'est pas cliquable.
"""
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from .models import StatusSubscriber


class LienConfirmationAbsoluTests(TestCase):
    def test_lien_confirmation_absolu(self):
        resp = APIClient().post(
            '/api/django/statuspage/public/abonner/',
            {'email': 'abs@example.com'})
        self.assertEqual(resp.status_code, 202)
        abonne = StatusSubscriber.objects.get(email='abs@example.com')
        self.assertEqual(len(mail.outbox), 1)
        attendu_fin = (
            '/api/django/statuspage/public/confirmer/'
            f'{abonne.token_desabonnement}/')
        lien = next(
            mot for mot in mail.outbox[0].body.split()
            if mot.endswith(attendu_fin))
        self.assertTrue(
            lien.startswith(('http://', 'https://')),
            f'lien non absolu : {lien}')
