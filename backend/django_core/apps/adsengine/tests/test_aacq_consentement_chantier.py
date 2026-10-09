"""AACQ6 — le consentement photo doit être celui du client du chantier, et
``ConsentRecord.client_id`` est figé après création."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.adsengine import creative_factory as cf
from apps.adsengine.models import ConsentRecord, CreativeAsset
from apps.roles.models import Role

A, B = 41, 42


class _Att:
    file_key = 'chantier/7/p.jpg'


def _consent(company, client_id):
    return ConsentRecord.objects.create(
        company=company, client_id=client_id, client_nom='C',
        portee_photo=True, date_consentement=datetime.date(2026, 1, 1))


class ConsentementChantierTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AACQ6 Co', slug='aacq6-co')
        role = Role.objects.create(
            company=self.company, nom='ads', permissions=['adsengine_manage'])
        user = get_user_model().objects.create_user(
            username='aacq6', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self.consent_b = _consent(self.company, B)
        for target, rv in (
                ('chantier_photo', _Att()), ('chantier_ville', 'Fès')):
            p = mock.patch(f'apps.installations.selectors.{target}',
                           return_value=rv)
            p.start()
            self.addCleanup(p.stop)

    def _owner(self, value):
        p = mock.patch('apps.installations.selectors.chantier_client_id',
                       return_value=value)
        p.start()
        self.addCleanup(p.stop)

    def _post(self, client_id):
        return self.api.post(
            '/api/django/adsengine/creatifs/import-chantier/',
            {'chantier_id': 7, 'attachment_id': 99, 'client_id': client_id},
            format='json')

    def test_consentement_autre_client_refuse_vue(self):
        self._owner(A)
        resp = self._post(B)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['blocked_reason'], 'consentement_manquant')
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_consentement_autre_client_refuse_service(self):
        self._owner(A)
        res = cf.import_chantier_photo(
            self.company, chantier_id=7, attachment_id=99, client_id=B)
        self.assertFalse(res['imported'])
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_chantier_sans_client_refuse(self):
        self._owner(None)
        res = cf.import_chantier_photo(
            self.company, chantier_id=7, attachment_id=99, client_id=B)
        self.assertFalse(res['imported'])

    def test_client_id_fige_au_patch(self):
        resp = self.api.patch(
            f'/api/django/adsengine/consentements/{self.consent_b.pk}/',
            {'client_id': 999999}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.consent_b.refresh_from_db()
        self.assertEqual(self.consent_b.client_id, B)

    def test_meme_client_accepte(self):
        _consent(self.company, A)
        self._owner(A)
        resp = self._post(A)
        self.assertEqual(resp.status_code, 201, resp.content)
