"""YSERV4 — ``core.events.chantier_receptionne`` est émis aux DEUX sites où le
chantier atteint le statut canonique RECEPTIONNE : ``PATCH .../chantiers/<id>/``
(``perform_update``) et l'action ``mise-en-service`` (qui se rabat sur
RECEPTIONNE). Émis exactement une fois par franchissement (jamais au
re-passage) — ``apps.compta`` s'y abonne pour créer l'enquête NPS (test dédié
côté compta) ; ici on vérifie uniquement le CONTRAT d'émission côté
``installations`` avec un récepteur de test jetable.

Run :
    python manage.py test apps.installations.tests_yserv4_event -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from core.events import chantier_receptionne

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'yserv4-view-co-{n}', defaults={'nom': f'YSERV4 View Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'yserv4-view-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='YSERV4',
        email=f'yserv4-view-{n}@example.invalid')


def make_installation(company, client, statut=Installation.Statut.INSTALLE):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-YSERV4-{n}', client=client,
        statut=statut)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _SignalCatcher:
    """Récepteur jetable : compte les émissions et capture le dernier appel,
    sans dépendre d'un abonné réel (compta) déjà câblé."""

    def __init__(self):
        self.calls = []

    def __call__(self, sender, installation, user, ancien_statut, **kwargs):
        self.calls.append({
            'installation_id': installation.id,
            'user': user,
            'ancien_statut': ancien_statut,
        })


class TestChantierReceptionneEmisViaPerformUpdate(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.inst = make_installation(self.company, self.client_obj)
        self.catcher = _SignalCatcher()
        chantier_receptionne.connect(
            self.catcher, dispatch_uid='test-yserv4-catcher-update')

    def tearDown(self):
        chantier_receptionne.disconnect(
            dispatch_uid='test-yserv4-catcher-update')

    def test_patch_to_receptionne_emits_once(self):
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(self.catcher.calls), 1)
        self.assertEqual(self.catcher.calls[0]['installation_id'], self.inst.id)
        self.assertEqual(self.catcher.calls[0]['ancien_statut'],
                         Installation.Statut.INSTALLE)

    def test_repatch_same_statut_does_not_reemit(self):
        api = auth(self.user)
        api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')
        # Re-sauvegarde sans changement de statut canonique (ex. autre champ).
        api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')
        self.assertEqual(len(self.catcher.calls), 1)

    def test_patch_not_reaching_receptionne_emits_nothing(self):
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(self.catcher.calls), 0)


class TestChantierReceptionneEmisViaMiseEnService(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.inst = make_installation(self.company, self.client_obj)
        self.catcher = _SignalCatcher()
        chantier_receptionne.connect(
            self.catcher, dispatch_uid='test-yserv4-catcher-mes')

    def tearDown(self):
        chantier_receptionne.disconnect(
            dispatch_uid='test-yserv4-catcher-mes')

    def test_mise_en_service_emits_once(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(self.catcher.calls), 1)
        self.assertEqual(self.catcher.calls[0]['installation_id'], self.inst.id)
