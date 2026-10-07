"""ADOC126 — un chantier ANNULÉ est introuvable (404) au portail client.

Constat C-ADOC-047 (C13, S3) — sonde #88 : absent de la liste « Mes
chantiers » (``annule=False``) mais servi en détail — HTTP 500 (TypeError
« 'NoneType' object is not a mapping » : la ligne de liste manque), photos et
photo servies. ``chantier_du_client_portail_obj`` exclut désormais
``annule=True`` comme la liste.

Run :
    python manage.py test apps.installations.tests_adoc_chantier_annule_portail -v2
"""
import itertools
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.selectors import chantier_du_client_portail_obj
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)
BASE = '/api/django/portail/mes-chantiers'


class ChantierAnnulePortailTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc126-co-{n}', nom=f'ADOC126 Co {n}')
        self.client_a = Client.objects.create(
            company=self.company, nom='Amrani', prenom=f'ADOC126-{n}',
            email=f'adoc126-{n}@example.invalid')
        self.actif = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC126-A-{n}',
            client=self.client_a, site_ville='Rabat')
        self.annule = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC126-X-{n}',
            client=self.client_a, site_ville='Rabat', annule=True)
        ct = ContentType.objects.get_for_model(Installation)
        self.photo = Attachment.objects.create(
            company=self.company, content_type=ct, object_id=self.annule.id,
            file_key=f'attachments/adoc126-{n}.jpg', filename='p.jpg',
            size=10, mime='image/jpeg', phase='avant')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        user = CustomUser.objects.create_user(
            username=f'adoc126-portail-{n}', password='motdepasse-test-1234',
            company=self.company, role=role)
        user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        user.portail_client_id = self.client_a.id
        user.save()
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def test_detail_chantier_annule_404(self):
        liste = self.api.get(f'{BASE}/')
        ids = {ligne['id'] for ligne in liste.data['results']}
        self.assertNotIn(self.annule.id, ids)
        res = self.api.get(f'{BASE}/{self.annule.id}/')
        self.assertEqual(res.status_code, 404)

    def test_photos_chantier_annule_404(self):
        res = self.api.get(f'{BASE}/{self.annule.id}/photos/')
        self.assertEqual(res.status_code, 404)

    def test_photo_chantier_annule_404(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'\xff\xd8\xff', None)):
            res = self.api.get(
                f'{BASE}/{self.annule.id}/photo/{self.photo.id}/')
        self.assertEqual(res.status_code, 404)

    def test_tableau_de_bord_ignore_le_chantier_annule(self):
        res = self.api.get(
            '/api/django/portail/client/tableau-de-bord/',
            {'chantier': self.annule.id})
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data.get('prochain_jalon'))

    def test_selecteur_exclut_annule_garde_actif(self):
        self.assertIsNone(chantier_du_client_portail_obj(
            self.company, self.client_a.id, self.annule.id))
        self.assertEqual(chantier_du_client_portail_obj(
            self.company, self.client_a.id, self.actif.id), self.actif)
        res = self.api.get(f'{BASE}/{self.actif.id}/')
        self.assertEqual(res.status_code, 200)
