"""Tests XKB7 — Lecture obligatoire d'articles KB.

Couvre :
* assigner un article à un utilisateur explicite ou à un palier de rôle ;
* le rapport de conformité (lus/non-lus) reflète les ``KbLecture`` (KB7)
  existantes sans les dupliquer ;
* la relance (``services.relancer_lectures_obligatoires``) notifie SEULEMENT
  les non-lecteurs, jamais les déjà-lus ;
* société posée côté serveur, isolation cross-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import KbArticle, KbLectureObligatoire
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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class KbLectureObligatoireApiTests(TestCase):
    BASE = '/api/django/kb/lectures-obligatoires/'
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co_a = make_company('kb-lo-a', 'A')
        self.co_b = make_company('kb-lo-b', 'B')
        self.admin_a = make_user(self.co_a, 'kb-lo-admin-a', role='admin')
        self.user_a = make_user(self.co_a, 'kb-lo-user-a')
        self.user_b = make_user(self.co_b, 'kb-lo-user-b')
        self.article_a = KbArticle.objects.create(
            company=self.co_a, titre='SOP A', statut=KbArticle.Statut.PUBLIE)
        self.article_b = KbArticle.objects.create(
            company=self.co_b, titre='SOP B', statut=KbArticle.Statut.PUBLIE)

    def test_assign_to_user_forces_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post(self.BASE, {
            'article': self.article_a.id, 'utilisateur': self.user_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbLectureObligatoire.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_assign_requires_exactly_one_target(self):
        api = auth(self.admin_a)
        # Ni utilisateur ni rôle.
        resp = api.post(self.BASE, {'article': self.article_a.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        # Les deux à la fois.
        resp2 = api.post(self.BASE, {
            'article': self.article_a.id, 'utilisateur': self.user_a.id,
            'role_cible': 'normal',
        }, format='json')
        self.assertEqual(resp2.status_code, 400, resp2.data)

    def test_assign_rejects_cross_tenant_article(self):
        api = auth(self.admin_a)
        resp = api.post(self.BASE, {
            'article': self.article_b.id, 'utilisateur': self.user_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_role_cible_assignation_covers_all_users_of_tier(self):
        normal1 = make_user(self.co_a, 'kb-lo-n1', role='normal')
        normal2 = make_user(self.co_a, 'kb-lo-n2', role='normal')
        assignation = KbLectureObligatoire.objects.create(
            company=self.co_a, article=self.article_a, role_cible='normal')
        assignees = {u.id for u in selectors.assignees_for_assignation(
            assignation)}
        self.assertEqual(assignees, {normal1.id, normal2.id})

    def test_rapport_conformite_distinguishes_lu_non_lu(self):
        lecteur = make_user(self.co_a, 'kb-lo-lecteur')
        non_lecteur = make_user(self.co_a, 'kb-lo-non-lecteur')
        KbLectureObligatoire.objects.create(
            company=self.co_a, article=self.article_a, utilisateur=lecteur)
        KbLectureObligatoire.objects.create(
            company=self.co_a, article=self.article_a, utilisateur=non_lecteur)
        services.marquer_lu(self.article_a, utilisateur=lecteur)
        rapport = selectors.rapport_conformite_article(self.article_a)
        lus_ids = {r['utilisateur'] for r in rapport['lus']}
        non_lus_ids = {r['utilisateur'] for r in rapport['non_lus']}
        self.assertIn(lecteur.id, lus_ids)
        self.assertIn(non_lecteur.id, non_lus_ids)
        self.assertNotIn(lecteur.id, non_lus_ids)

    def test_rapport_conformite_endpoint(self):
        non_lecteur = make_user(self.co_a, 'kb-lo-endpoint-nl')
        KbLectureObligatoire.objects.create(
            company=self.co_a, article=self.article_a, utilisateur=non_lecteur)
        resp = auth(self.admin_a).get(
            f'{self.ARTICLES}{self.article_a.id}/rapport-conformite/')
        self.assertEqual(resp.status_code, 200, resp.data)
        non_lus_ids = {r['utilisateur'] for r in resp.data['non_lus']}
        self.assertIn(non_lecteur.id, non_lus_ids)

    def test_list_isolation_cross_tenant(self):
        KbLectureObligatoire.objects.create(
            company=self.co_a, article=self.article_a, utilisateur=self.user_a)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)


class KbLectureObligatoireRelanceTests(TestCase):
    """Relance : notifie seulement les non-lecteurs, jamais les déjà-lus."""

    def setUp(self):
        self.co = make_company('kb-lo-relance', 'R')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Consignes', statut=KbArticle.Statut.PUBLIE)
        self.lecteur = make_user(self.co, 'kb-lo-r-lecteur')
        self.non_lecteur = make_user(self.co, 'kb-lo-r-non-lecteur')
        KbLectureObligatoire.objects.create(
            company=self.co, article=self.article, utilisateur=self.lecteur)
        KbLectureObligatoire.objects.create(
            company=self.co, article=self.article, utilisateur=self.non_lecteur)
        services.marquer_lu(self.article, utilisateur=self.lecteur)

    def test_relance_notifies_only_non_readers(self):
        total = services.relancer_lectures_obligatoires(company=self.co)
        self.assertEqual(total, 1)
        notified_ids = set(
            Notification.objects.filter(recipient=self.non_lecteur)
            .values_list('recipient_id', flat=True))
        self.assertIn(self.non_lecteur.id, notified_ids)
        self.assertFalse(
            Notification.objects.filter(recipient=self.lecteur).exists())

    def test_relance_skips_unpublished_article(self):
        self.article.statut = KbArticle.Statut.BROUILLON
        self.article.save(update_fields=['statut'])
        total = services.relancer_lectures_obligatoires(company=self.co)
        self.assertEqual(total, 0)

    def test_relance_is_idempotent_and_never_raises(self):
        services.relancer_lectures_obligatoires(company=self.co)
        # Un second appel ne doit ni lever ni dupliquer anormalement — il
        # ré-émet simplement une notification pour le non-lecteur toujours
        # non-lu (comportement idempotent au sens FG1 : pas de mutation
        # métier, une notification de plus est acceptable).
        total2 = services.relancer_lectures_obligatoires(company=self.co)
        self.assertEqual(total2, 1)
