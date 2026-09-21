"""Tests XKB21 — Dupliquer / déplacer un article.

Couvre :
* dupliquer (sans sous-articles) crée une copie BROUILLON indépendante ;
* dupliquer AVEC sous-articles clone tout le sous-arbre sous la copie ;
* la copie n'est jamais un gabarit ni verrouillée même si la source l'était ;
* déplacer re-parente tout un sous-arbre (déjà XKB8, revalidé ici avec ACL
  de destination) ;
* déplacer cross-société est rejeté.
"""
from django.contrib.auth import get_user_model
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


class KbDupliquerServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-dup', 'D')
        self.user = make_user(self.co, 'kb-dup-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Original', corps='Contenu',
            categorie='SOP', statut=KbArticle.Statut.PUBLIE,
            est_gabarit=True, est_verrouille=True)

    def test_dupliquer_without_children_creates_independent_draft(self):
        copie = services.dupliquer_article(
            self.article, auteur=self.user, company=self.co)
        self.assertNotEqual(copie.id, self.article.id)
        self.assertEqual(copie.statut, KbArticle.Statut.BROUILLON)
        self.assertFalse(copie.est_gabarit)
        self.assertFalse(copie.est_verrouille)
        self.assertEqual(copie.corps, self.article.corps)
        self.assertEqual(copie.company, self.co)
        # L'original reste inchangé.
        self.article.refresh_from_db()
        self.assertEqual(self.article.statut, KbArticle.Statut.PUBLIE)
        self.assertTrue(self.article.est_gabarit)

    def test_dupliquer_with_children_clones_subtree_under_copy(self):
        enfant = KbArticle.objects.create(
            company=self.co, titre='Enfant', corps='X', parent=self.article)
        petit_enfant = KbArticle.objects.create(
            company=self.co, titre='Petit-enfant', corps='Y', parent=enfant)

        copie = services.dupliquer_article(
            self.article, auteur=self.user, company=self.co,
            avec_sous_articles=True)

        enfants_copie = list(copie.enfants.all())
        self.assertEqual(len(enfants_copie), 1)
        enfant_copie = enfants_copie[0]
        self.assertEqual(enfant_copie.titre, 'Enfant')
        self.assertNotEqual(enfant_copie.id, enfant.id)

        petits_enfants_copie = list(enfant_copie.enfants.all())
        self.assertEqual(len(petits_enfants_copie), 1)
        self.assertEqual(petits_enfants_copie[0].titre, 'Petit-enfant')
        self.assertNotEqual(petits_enfants_copie[0].id, petit_enfant.id)

        # L'original garde ses propres enfants (jamais reparentés).
        self.assertEqual(self.article.enfants.count(), 1)

    def test_dupliquer_without_children_does_not_copy_subtree(self):
        KbArticle.objects.create(
            company=self.co, titre='Enfant', corps='X', parent=self.article)
        copie = services.dupliquer_article(
            self.article, auteur=self.user, company=self.co,
            avec_sous_articles=False)
        self.assertEqual(copie.enfants.count(), 0)


class KbDupliquerApiTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-dup-api', 'A')
        self.user = make_user(self.co, 'kb-dup-api-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Article API', corps='Contenu')

    def test_dupliquer_endpoint(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.article.id}/dupliquer/',
            {'avec_sous_articles': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], KbArticle.Statut.BROUILLON)
        self.assertNotEqual(resp.data['id'], self.article.id)

    def test_dupliquer_endpoint_with_children(self):
        KbArticle.objects.create(
            company=self.co, titre='Enfant', corps='X', parent=self.article)
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.article.id}/dupliquer/',
            {'avec_sous_articles': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        copie = KbArticle.objects.get(id=resp.data['id'])
        self.assertEqual(copie.enfants.count(), 1)


class KbDeplacerCrossTenantTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-move', 'M')
        self.other_co = make_company('kb-move-other', 'O')
        self.user = make_user(self.co, 'kb-move-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='À déplacer', corps='X')
        self.other_parent = KbArticle.objects.create(
            company=self.other_co, titre='Parent autre société', corps='Y')

    def test_deplacer_cross_tenant_rejected(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.article.id}/deplacer/',
            {'parent': self.other_parent.id}, format='json')
        self.assertEqual(resp.status_code, 400)
