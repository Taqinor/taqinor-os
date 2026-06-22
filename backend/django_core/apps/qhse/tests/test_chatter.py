"""Tests QHSE14 — Chatter QHSE (NCR / CAPA / Incident / Audit).

Couvre :

* les helpers ``chatter.log_creation`` / ``log_field_change`` / ``log_note`` et
  le mapping de cible (NCR/CAPA) ;
* ``log_field_change`` n'écrit RIEN quand la valeur n'a pas changé ;
* via l'API : la création d'une NCR/CAPA trace une entrée ``creation`` ; un
  PATCH d'un champ suivi trace une ``modification`` ; ``noter`` ajoute une note ;
  ``historique`` renvoie l'historique ordonné ;
* isolation société sur l'endpoint chatter en lecture seule + palier
  Responsable/Admin.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse import chatter
from apps.qhse.models import (
    ActionCorrectivePreventive, NonConformite, QhseChatterEntry,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChatterHelperTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse14-h', 'H')
        self.user = make_user(self.co, 'qhse14-h')
        self.ncr = NonConformite.objects.create(company=self.co, titre='NCR')

    def test_cible_type_mapping(self):
        self.assertEqual(
            chatter.cible_type_for(self.ncr), QhseChatterEntry.Cible.NCR)
        capa = ActionCorrectivePreventive.objects.create(
            company=self.co, non_conformite=self.ncr, description='x')
        self.assertEqual(
            chatter.cible_type_for(capa), QhseChatterEntry.Cible.CAPA)

    def test_log_creation_and_note(self):
        chatter.log_creation(self.ncr, self.user)
        chatter.log_note(self.ncr, self.user, 'À surveiller')
        entries = chatter.chatter_for(
            self.co, QhseChatterEntry.Cible.NCR, self.ncr.id)
        kinds = set(entries.values_list('kind', flat=True))
        self.assertEqual(
            kinds,
            {QhseChatterEntry.Kind.CREATION, QhseChatterEntry.Kind.NOTE})

    def test_field_change_noop_when_equal(self):
        none_entry = chatter.log_field_change(
            self.ncr, self.user, 'statut', 'ouverte', 'ouverte', label='Statut')
        self.assertIsNone(none_entry)
        entry = chatter.log_field_change(
            self.ncr, self.user, 'statut', 'ouverte', 'cloturee',
            label='Statut')
        self.assertIsNotNone(entry)
        self.assertEqual(entry.old_value, 'ouverte')
        self.assertEqual(entry.new_value, 'cloturee')


class ChatterApiTests(TestCase):
    NCR_BASE = '/api/django/qhse/non-conformites/'

    def setUp(self):
        self.co = make_company('qhse14-api', 'Api')
        self.user = make_user(self.co, 'qhse14-api')

    def _entries(self, ncr_id):
        return QhseChatterEntry.objects.filter(
            company=self.co, cible_type=QhseChatterEntry.Cible.NCR,
            cible_id=ncr_id)

    def test_create_logs_creation(self):
        resp = auth(self.user).post(
            self.NCR_BASE, {'titre': 'Câble dénudé'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        entries = self._entries(resp.data['id'])
        self.assertEqual(entries.count(), 1)
        self.assertEqual(
            entries.first().kind, QhseChatterEntry.Kind.CREATION)

    def test_patch_logs_field_change(self):
        ncr = NonConformite.objects.create(company=self.co, titre='NCR')
        resp = auth(self.user).patch(
            f'{self.NCR_BASE}{ncr.id}/', {'statut': 'cloturee'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        mods = self._entries(ncr.id).filter(
            kind=QhseChatterEntry.Kind.MODIFICATION)
        self.assertEqual(mods.count(), 1)
        self.assertEqual(mods.first().field, 'statut')

    def test_noter_and_historique(self):
        ncr = NonConformite.objects.create(company=self.co, titre='NCR')
        note = auth(self.user).post(
            f'{self.NCR_BASE}{ncr.id}/noter/',
            {'body': 'Relancer le poseur'}, format='json')
        self.assertEqual(note.status_code, 201, note.data)
        hist = auth(self.user).get(f'{self.NCR_BASE}{ncr.id}/historique/')
        self.assertEqual(hist.status_code, 200, hist.data)
        bodies = [e['body'] for e in hist.data]
        self.assertIn('Relancer le poseur', bodies)

    def test_noter_requires_body(self):
        ncr = NonConformite.objects.create(company=self.co, titre='NCR')
        resp = auth(self.user).post(
            f'{self.NCR_BASE}{ncr.id}/noter/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_chatter_endpoint_isolation(self):
        ncr = NonConformite.objects.create(company=self.co, titre='NCR')
        chatter.log_note(ncr, self.user, 'note A')
        other = make_company('qhse14-api-b', 'B')
        other_user = make_user(other, 'qhse14-api-b')
        resp = auth(other_user).get(
            f'/api/django/qhse/chatter/?cible_type=ncr&cible_id={ncr.id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse14-normal', role='normal')
        resp = auth(normal).get('/api/django/qhse/chatter/')
        self.assertEqual(resp.status_code, 403)
