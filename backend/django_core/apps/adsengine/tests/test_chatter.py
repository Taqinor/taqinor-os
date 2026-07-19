"""PUB55 — Chatter de campagne/ad (fil unique : notes + événements auto).

Prouve : une note posée (acteur + société côté serveur) ET les événements auto
(action appliquée, alerte) apparaissent dans UN SEUL fil chronologique par
entité ; la fusion company-scopée ne fabrique aucun doublon.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import chatter
from apps.adsengine.models import (
    AdEngineActivity, EngineAction, EngineAlert,
)

User = get_user_model()

BASE = '/api/django/adsengine/chatter/'


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


class ChatterTimelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Chat Co', slug='chat-co')
        self.user = make_user(
            self.company, 'chat_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_merged_timeline_has_note_and_auto_events(self):
        # Note manuelle.
        AdEngineActivity.objects.create(
            company=self.company, entity_type='campaign',
            entity_meta_id='camp-1', body='Budget baissé pour Ramadan.',
            user=self.user)
        # Action appliquée ciblant la campagne (événement auto).
        EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='Dépense sans lead — pause.',
            status=EngineAction.Statut.APPLIQUEE,
            applied_at=timezone.now(),
            payload={'target_meta_id': 'camp-1', 'target_type': 'campaign'})
        # Alerte de la campagne (entity_key 'campaign:camp-1').
        EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.GARDE_FOU,
            message='Plafond quotidien dépassé.', entity_key='campaign:camp-1')

        timeline = chatter.build_timeline(self.company, 'campaign', 'camp-1')
        kinds = {i['kind'] for i in timeline}
        self.assertEqual(kinds, {'note', 'action_applied', 'alert'})
        self.assertEqual(len(timeline), 3)

    def test_timeline_scoped_to_entity(self):
        AdEngineActivity.objects.create(
            company=self.company, entity_type='campaign',
            entity_meta_id='camp-1', body='note A', user=self.user)
        AdEngineActivity.objects.create(
            company=self.company, entity_type='campaign',
            entity_meta_id='camp-2', body='note B', user=self.user)
        timeline = chatter.build_timeline(self.company, 'campaign', 'camp-1')
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]['body'], 'note A')

    def test_applied_action_for_other_entity_excluded(self):
        EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='pause', status=EngineAction.Statut.APPLIQUEE,
            payload={'target_meta_id': 'camp-999'})
        timeline = chatter.build_timeline(self.company, 'campaign', 'camp-1')
        self.assertEqual(timeline, [])


class ChatterApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Api Chat', slug='api-chat')
        self.user = make_user(
            self.company, 'api_chat_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_post_note_forces_user_and_company(self):
        resp = auth(self.user).post(BASE, {
            'entity_type': 'ad', 'entity_id': 'ad-7',
            'body': 'Créatif fatigué, à roter.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = AdEngineActivity.objects.get(id=resp.data['id'])
        self.assertEqual(note.company_id, self.company.id)
        self.assertEqual(note.user_id, self.user.id)
        self.assertEqual(resp.data['author'], self.user.username)

    def test_get_timeline_endpoint(self):
        AdEngineActivity.objects.create(
            company=self.company, entity_type='ad', entity_meta_id='ad-7',
            body='une note', user=self.user)
        resp = auth(self.user).get(f'{BASE}?entity_type=ad&entity_id=ad-7')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['kind'], 'note')

    def test_bad_entity_type_rejected(self):
        resp = auth(self.user).get(f'{BASE}?entity_type=widget&entity_id=x')
        self.assertEqual(resp.status_code, 400)

    def test_empty_note_rejected(self):
        resp = auth(self.user).post(BASE, {
            'entity_type': 'ad', 'entity_id': 'ad-7', 'body': '  ',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
