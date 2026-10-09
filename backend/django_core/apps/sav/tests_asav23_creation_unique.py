"""ASAV23 — un double envoi de création ne crée qu'un ticket.

Deux POST identiques (même société, client, chantier, équipement,
description normalisée) à moins de 60 s : le second reçoit 409 avec la
référence existante. Hors fenêtre, ou description différente : 201.

Run :
    python manage.py test apps.sav.tests_asav23_creation_unique -v2
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket

User = get_user_model()
URL = '/api/django/sav/tickets/'


class CreationUniqueTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav23-co', defaults={'nom': 'ASAV23 Co'})
        self.admin = User.objects.create_user(
            username='asav23_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV23')

    def _post(self, description='Onduleur en défaut'):
        return self.api.post(URL, {
            'client': self.client_obj.pk, 'description': description,
            'priorite': 'normale'}, format='json')

    def _nb(self):
        return Ticket.objects.filter(client=self.client_obj).count()

    def test_double_post_409(self):
        r1 = self._post()
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self._post('  onduleur EN   défaut ')
        self.assertEqual(r2.status_code, 409, r2.content)
        self.assertEqual(r2.data['reference_existante'], r1.data['reference'])
        self.assertIn(r1.data['reference'], r2.data['detail'])
        self.assertEqual(self._nb(), 1)

    def test_hors_fenetre_cree(self):
        r1 = self._post()
        self.assertEqual(r1.status_code, 201, r1.content)
        plus_tard = timezone.now() + timedelta(seconds=61)
        with patch('django.utils.timezone.now', return_value=plus_tard):
            r2 = self._post()
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(self._nb(), 2)

    def test_description_differente_cree(self):
        self.assertEqual(self._post().status_code, 201)
        r2 = self._post('Panneau cassé')
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(self._nb(), 2)
