"""Tests XKB12 — Gabarits d'articles utilisateur.

Couvre :
* sauver un article comme gabarit (``est_gabarit`` bascule à True) ;
* créer un nouvel article depuis un gabarit pré-remplit titre/corps, en
  brouillon, et n'est PAS lui-même un gabarit ;
* la galerie de gabarits liste bien les gabarits (et pas les autres) ;
* les gabarits seedés (KB5, ``seed_kb_templates``) apparaissent dans la
  galerie ;
* isolation cross-tenant.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import services
from apps.kb.models import KbArticle

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


class KbGabaritsTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co_a = make_company('kb-gab-a', 'A')
        self.co_b = make_company('kb-gab-b', 'B')
        self.user_a = make_user(self.co_a, 'kb-gab-user-a')
        self.user_b = make_user(self.co_b, 'kb-gab-user-b')
        self.article = KbArticle.objects.create(
            company=self.co_a, titre='Modèle CR réunion',
            corps='# Ordre du jour', corps_format='markdown',
            categorie='Interne', tags='cr,reunion',
            statut=KbArticle.Statut.PUBLIE, auteur=self.user_a)

    def test_enregistrer_comme_gabarit_toggles_flag(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.ARTICLES}{self.article.id}/enregistrer-comme-gabarit/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.article.refresh_from_db()
        self.assertTrue(self.article.est_gabarit)

    def test_depuis_gabarit_creates_independent_draft(self):
        self.article.est_gabarit = True
        self.article.save(update_fields=['est_gabarit'])
        api = auth(self.user_a)
        resp = api.post(f'{self.ARTICLES}{self.article.id}/depuis-gabarit/')
        self.assertEqual(resp.status_code, 201, resp.data)
        new_id = resp.data['id']
        self.assertNotEqual(new_id, self.article.id)
        nouvel_article = KbArticle.objects.get(id=new_id)
        self.assertEqual(nouvel_article.titre, self.article.titre)
        self.assertEqual(nouvel_article.corps, self.article.corps)
        self.assertEqual(nouvel_article.statut, KbArticle.Statut.BROUILLON)
        self.assertFalse(nouvel_article.est_gabarit)
        self.assertEqual(nouvel_article.auteur_id, self.user_a.id)

    def test_service_creer_depuis_gabarit_forces_company_and_auteur(self):
        autre_user = make_user(self.co_a, 'kb-gab-autre')
        article = services.creer_depuis_gabarit(
            self.article, auteur=autre_user, company=self.co_a)
        self.assertEqual(article.company, self.co_a)
        self.assertEqual(article.auteur, autre_user)
        self.assertEqual(article.statut, KbArticle.Statut.BROUILLON)

    def test_gabarits_gallery_lists_only_templates(self):
        self.article.est_gabarit = True
        self.article.save(update_fields=['est_gabarit'])
        KbArticle.objects.create(
            company=self.co_a, titre='Article normal', auteur=self.user_a)
        resp = auth(self.user_a).get(f'{self.ARTICLES}gabarits/')
        self.assertEqual(resp.status_code, 200, resp.data)
        titres = {r['titre'] for r in rows(resp)}
        self.assertIn('Modèle CR réunion', titres)
        self.assertNotIn('Article normal', titres)

    def test_gabarits_gallery_isolation_cross_tenant(self):
        self.article.est_gabarit = True
        self.article.save(update_fields=['est_gabarit'])
        resp = auth(self.user_b).get(f'{self.ARTICLES}gabarits/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_seeded_templates_appear_in_gallery(self):
        call_command('seed_kb_templates', '--company', self.co_a.slug)
        resp = auth(self.user_a).get(f'{self.ARTICLES}gabarits/')
        titres = {r['titre'] for r in rows(resp)}
        self.assertIn(
            "Procédure d'installation — Résidentiel", titres)
        self.assertIn(
            "Dossier loi 82-21 — Autoconsommation (Checklist)", titres)
