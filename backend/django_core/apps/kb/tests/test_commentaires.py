"""Tests XKB13 — Commentaires sur articles KB.

Réutilise le chatter générique ``records.Comment`` (FG7) : le mécanisme
@mention→notify() EXISTE déjà (``records/views.py _notify_mentions``), ce
module ne le réécrit pas. Couvre le MANQUANT :
* commenter un article KB notifie l'AUTEUR de l'article (pas seulement les
  mentionnés) ;
* pas de self-notify (l'auteur qui commente son propre article) ;
* résolution de fil (``resolved``) — marquer résolu, filtrer ``?resolved=``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb.models import KbArticle
from apps.notifications.models import Notification
from apps.records.models import Comment

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class KbCommentairesTests(TestCase):
    COMMENTS = '/api/django/records/comments/'

    def setUp(self):
        self.co = make_company('kb-com', 'C')
        self.auteur = make_user(self.co, 'kb-com-auteur')
        self.collegue = make_user(self.co, 'kb-com-collegue')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Article commenté', auteur=self.auteur)

    def test_comment_notifies_article_author(self):
        api = auth(self.collegue)
        resp = api.post(self.COMMENTS, {
            'model': 'kb.kbarticle', 'id': self.article.id,
            'body': 'Bon article !',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            Notification.objects.filter(recipient=self.auteur).exists())

    def test_no_self_notify_when_author_comments_own_article(self):
        api = auth(self.auteur)
        resp = api.post(self.COMMENTS, {
            'model': 'kb.kbarticle', 'id': self.article.id,
            'body': 'Petite précision.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(
            Notification.objects.filter(recipient=self.auteur).exists())

    def test_comment_on_non_kb_target_does_not_crash(self):
        # Garde de robustesse : un commentaire sur une cible NON-kb ne doit
        # jamais lever, même si le récepteur XKB13 tourne pour tous les
        # Comment (il doit se reconnaître hors-scope et sortir proprement).
        from apps.crm.models import Lead
        lead = Lead.objects.create(company=self.co, nom='Prospect')
        api = auth(self.collegue)
        resp = api.post(self.COMMENTS, {
            'model': 'crm.lead', 'id': lead.id, 'body': 'Suivi.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_mark_resolved(self):
        comment = Comment.objects.create(
            company=self.co, content_type_id=self._kb_ct_id(),
            object_id=self.article.id, body='Fil', author=self.collegue)
        api = auth(self.auteur)
        resp = api.patch(
            f'{self.COMMENTS}{comment.id}/', {'resolved': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        comment.refresh_from_db()
        self.assertTrue(comment.resolved)

    def test_filter_by_resolved(self):
        ct_id = self._kb_ct_id()
        resolu = Comment.objects.create(
            company=self.co, content_type_id=ct_id, object_id=self.article.id,
            body='Résolu', author=self.collegue, resolved=True)
        non_resolu = Comment.objects.create(
            company=self.co, content_type_id=ct_id, object_id=self.article.id,
            body='Ouvert', author=self.collegue, resolved=False)
        api = auth(self.auteur)
        resp = api.get(
            f'{self.COMMENTS}?model=kb.kbarticle&id={self.article.id}'
            f'&resolved=false')
        ids = {r['id'] for r in rows(resp)}
        self.assertIn(non_resolu.id, ids)
        self.assertNotIn(resolu.id, ids)

    def _kb_ct_id(self):
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get(app_label='kb', model='kbarticle').id
