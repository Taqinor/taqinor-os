"""ADSDEEP53-56 — Tests des endpoints REST de la boîte de réception des
commentaires + des écrans Instagram (câblage front↔back — aucun nouveau
modèle, aucune logique métier ré-implémentée : les vues sont minces sur les
fonctions ``propose_*`` déjà construites de ``services.py``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import (
    CommentMirror, EngineAction, InstagramCommentMirror,
    InstagramMediaMirror,
)

User = get_user_model()


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


class CommentsInboxApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Comments Co', slug='cc')
        self.other_company = Company.objects.create(nom='Other Co', slug='oc')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.manager = make_user(
            self.company, 'manager', ['adsengine_view', 'adsengine_manage'])
        self.comment = CommentMirror.objects.create(
            company=self.company, meta_id='c1', object_meta_id='post1',
            source=CommentMirror.Source.POST, message='bonjour',
            from_name='Ali')
        self.other_comment = CommentMirror.objects.create(
            company=self.other_company, meta_id='c2', object_meta_id='post2',
            source=CommentMirror.Source.POST, message='hello')

    def test_list_returns_200_company_scoped(self):
        resp = auth(self.viewer).get('/api/django/adsengine/commentaires/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [row['id'] for row in resp.data]
        self.assertIn(self.comment.id, ids)
        self.assertNotIn(self.other_comment.id, ids)

    def test_counts_endpoint(self):
        resp = auth(self.viewer).get(
            '/api/django/adsengine/commentaires/compteurs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['unanswered'], 1)
        self.assertEqual(resp.data['hidden'], 0)

    def test_propose_hide_creates_one_engine_action(self):
        self.assertEqual(EngineAction.objects.filter(
            company=self.company).count(), 0)
        resp = auth(self.manager).post(
            f'/api/django/adsengine/commentaires/{self.comment.id}/masquer/',
            {'hidden': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        actions = EngineAction.objects.filter(company=self.company)
        self.assertEqual(actions.count(), 1)
        self.assertEqual(actions.first().kind, 'hide_comment')

    def test_propose_reply_creates_one_engine_action(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/commentaires/{self.comment.id}/repondre/',
            {'message': 'Merci !'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        actions = EngineAction.objects.filter(
            company=self.company, kind='reply_comment')
        self.assertEqual(actions.count(), 1)

    def test_propose_delete(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/commentaires/{self.comment.id}/supprimer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EngineAction.objects.filter(
            company=self.company, kind='delete_comment').count(), 1)

    def test_propose_private_reply(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/commentaires/{self.comment.id}'
            '/reponse-privee/', {'message': 'DM'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EngineAction.objects.filter(
            company=self.company, kind='private_reply').count(), 1)

    def test_reply_empty_message_is_400(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/commentaires/{self.comment.id}/repondre/',
            {'message': '  '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_company_isolation_returns_404(self):
        """Un commentaire d'une AUTRE société n'est jamais atteignable."""
        resp = auth(self.manager).post(
            '/api/django/adsengine/commentaires/'
            f'{self.other_comment.id}/masquer/', {'hidden': True},
            format='json')
        self.assertEqual(resp.status_code, 404)

    def test_write_requires_manage_permission(self):
        resp = auth(self.viewer).post(
            f'/api/django/adsengine/commentaires/{self.comment.id}/masquer/',
            {'hidden': True}, format='json')
        self.assertEqual(resp.status_code, 403)


class InstagramApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='IG Co', slug='igco')
        self.other_company = Company.objects.create(nom='IG Other', slug='igo')
        self.viewer = make_user(self.company, 'igviewer', ['adsengine_view'])
        self.manager = make_user(
            self.company, 'igmanager',
            ['adsengine_view', 'adsengine_manage'])
        self.media = InstagramMediaMirror.objects.create(
            company=self.company, meta_id='m1', caption='hello world',
            media_type='IMAGE')
        self.other_media = InstagramMediaMirror.objects.create(
            company=self.other_company, meta_id='m2', caption='other')
        self.comment = InstagramCommentMirror.objects.create(
            company=self.company, meta_id='ic1', media_meta_id='m1',
            message='nice', from_username='bob')
        self.other_comment = InstagramCommentMirror.objects.create(
            company=self.other_company, meta_id='ic2', media_meta_id='m2',
            message='other')

    def test_media_list_company_scoped(self):
        resp = auth(self.viewer).get('/api/django/adsengine/instagram/medias/')
        self.assertEqual(resp.status_code, 200, resp.data)
        metas = [row['meta_id'] for row in resp.data]
        self.assertIn('m1', metas)
        self.assertNotIn('m2', metas)

    def test_comments_list_company_scoped(self):
        resp = auth(self.viewer).get(
            '/api/django/adsengine/instagram/commentaires/')
        self.assertEqual(resp.status_code, 200, resp.data)
        metas = [row['meta_id'] for row in resp.data]
        self.assertIn('ic1', metas)
        self.assertNotIn('ic2', metas)

    def test_quota_empty_is_none_safe(self):
        resp = auth(self.viewer).get('/api/django/adsengine/instagram/quota/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['used'])
        self.assertIsNone(resp.data['total'])

    def test_propose_publish_creates_one_engine_action(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/instagram/publier/',
            {'media_type': 'IMAGE', 'image_url': 'https://x/img.jpg',
             'caption': 'Bonjour'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        actions = EngineAction.objects.filter(
            company=self.company, kind='publish_ig')
        self.assertEqual(actions.count(), 1)

    def test_propose_publish_invalid_media_type_is_400(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/instagram/publier/',
            {'media_type': 'BOGUS'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_propose_hide_comment(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/instagram/commentaires/{self.comment.id}'
            '/masquer/', {'hidden': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EngineAction.objects.filter(
            company=self.company, kind='hide_ig_comment').count(), 1)

    def test_propose_reply_comment(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/instagram/commentaires/{self.comment.id}'
            '/repondre/', {'message': 'merci'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EngineAction.objects.filter(
            company=self.company, kind='reply_ig_comment').count(), 1)

    def test_propose_delete_comment(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/instagram/commentaires/{self.comment.id}'
            '/supprimer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EngineAction.objects.filter(
            company=self.company, kind='delete_ig_comment').count(), 1)

    def test_propose_toggle_comments_by_meta_id(self):
        resp = auth(self.manager).post(
            f'/api/django/adsengine/instagram/medias/{self.media.meta_id}'
            '/commentaires-actif/', {'enabled': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EngineAction.objects.filter(
            company=self.company, kind='toggle_ig_comments').count(), 1)

    def test_company_isolation_media_toggle_404(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/instagram/medias/'
            f'{self.other_media.meta_id}/commentaires-actif/',
            {'enabled': False}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_company_isolation_comment_hide_404(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/instagram/commentaires/'
            f'{self.other_comment.id}/masquer/', {'hidden': True},
            format='json')
        self.assertEqual(resp.status_code, 404)

    def test_write_requires_manage_permission(self):
        resp = auth(self.viewer).post(
            '/api/django/adsengine/instagram/publier/',
            {'media_type': 'IMAGE', 'image_url': 'https://x/img.jpg'},
            format='json')
        self.assertEqual(resp.status_code, 403)
