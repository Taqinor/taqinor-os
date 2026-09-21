"""Tests XKB14 — Vérification, péremption & verrou d'article.

Couvre :
* ``verifier`` pose ``verifie_par``/``verifie_jusqua`` (badge « Vérifié ») ;
* le rapport de péremption liste les articles dont ``verifie_jusqua`` est
  dépassée ;
* la relance (sweep) notifie le vérificateur des articles périmés ;
* ``verrouiller``/``deverrouiller`` + un PATCH sur article verrouillé est 403
  pour qui n'a pas d'ACL d'édition, 200 pour l'admin/titulaire d'ACL édition.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import KbArticle, KbArticleAcl
from apps.notifications.models import Notification

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


class KbVerificationTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-verif', 'V')
        self.verificateur = make_user(self.co, 'kb-verif-user')
        self.article = KbArticle.objects.create(company=self.co, titre='SOP')

    def test_verifier_sets_badge_fields(self):
        api = auth(self.verificateur)
        resp = api.post(
            f'{self.ARTICLES}{self.article.id}/verifier/',
            {'horizon_jours': 30}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.article.refresh_from_db()
        self.assertEqual(self.article.verifie_par_id, self.verificateur.id)
        self.assertIsNotNone(self.article.verifie_jusqua)
        self.assertGreater(self.article.verifie_jusqua, timezone.now())

    def test_verifier_default_horizon_90_days(self):
        services.verifier_article(self.article, verificateur=self.verificateur)
        delta = self.article.verifie_jusqua - timezone.now()
        self.assertGreater(delta, timedelta(days=89))
        self.assertLess(delta, timedelta(days=91))


class KbPeremptionTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-perim', 'P')
        self.verificateur = make_user(self.co, 'kb-perim-user')
        self.article_perime = KbArticle.objects.create(
            company=self.co, titre='Périmé')
        services.verifier_article(
            self.article_perime, verificateur=self.verificateur, horizon_jours=0)
        # Force la date dans le passé (horizon_jours=0 = maintenant, pas encore
        # strictement dépassé selon le moment exact de l'assertion).
        self.article_perime.verifie_jusqua = timezone.now() - timedelta(days=1)
        self.article_perime.save(update_fields=['verifie_jusqua'])
        self.article_ok = KbArticle.objects.create(company=self.co, titre='OK')
        services.verifier_article(
            self.article_ok, verificateur=self.verificateur, horizon_jours=90)

    def test_rapport_peremption_lists_only_expired(self):
        rapport = selectors.rapport_peremption(self.co)
        ids = {r['id'] for r in rapport}
        self.assertIn(self.article_perime.id, ids)
        self.assertNotIn(self.article_ok.id, ids)

    def test_rapport_peremption_endpoint(self):
        resp = auth(self.verificateur).get(
            '/api/django/kb/articles/rapport-peremption/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in resp.data}
        self.assertIn(self.article_perime.id, ids)

    def test_relance_notifies_verificateur(self):
        total = services.relancer_revues_perimees(company=self.co)
        self.assertEqual(total, 1)
        self.assertTrue(
            Notification.objects.filter(recipient=self.verificateur).exists())


class KbVerrouTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-verrou', 'L')
        self.admin = make_user(self.co, 'kb-verrou-admin', role='admin')
        self.editeur = make_user(self.co, 'kb-verrou-editeur')
        self.lecteur = make_user(self.co, 'kb-verrou-lecteur')
        self.article = KbArticle.objects.create(
            company=self.co, titre='SOP verrouillée', est_verrouille=True)
        KbArticleAcl.objects.create(
            company=self.co, article=self.article, utilisateur=self.editeur,
            niveau=KbArticleAcl.Niveau.EDITION)

    def test_patch_rejected_for_user_without_edition_acl(self):
        resp = auth(self.lecteur).patch(
            f'{self.ARTICLES}{self.article.id}/',
            {'titre': 'Nouveau titre'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_patch_allowed_for_user_with_edition_acl(self):
        resp = auth(self.editeur).patch(
            f'{self.ARTICLES}{self.article.id}/',
            {'titre': 'Nouveau titre'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_patch_allowed_for_admin(self):
        resp = auth(self.admin).patch(
            f'{self.ARTICLES}{self.article.id}/',
            {'titre': 'Nouveau titre admin'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_deverrouiller_rejected_without_edition_acl(self):
        resp = auth(self.lecteur).post(
            f'{self.ARTICLES}{self.article.id}/deverrouiller/')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.article.refresh_from_db()
        self.assertTrue(self.article.est_verrouille)

    def test_deverrouiller_allowed_with_edition_acl(self):
        resp = auth(self.editeur).post(
            f'{self.ARTICLES}{self.article.id}/deverrouiller/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.article.refresh_from_db()
        self.assertFalse(self.article.est_verrouille)

    def test_verrouiller_action_locks_article(self):
        unlocked = KbArticle.objects.create(
            company=self.co, titre='Non verrouillé')
        resp = auth(self.admin).post(
            f'{self.ARTICLES}{unlocked.id}/verrouiller/')
        self.assertEqual(resp.status_code, 200, resp.data)
        unlocked.refresh_from_db()
        self.assertTrue(unlocked.est_verrouille)

    def test_unlocked_article_still_patchable_by_anyone_authorized(self):
        unlocked = KbArticle.objects.create(
            company=self.co, titre='Libre')
        resp = auth(self.lecteur).patch(
            f'{self.ARTICLES}{unlocked.id}/',
            {'titre': 'Modifié'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
