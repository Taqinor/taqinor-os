"""Tests XKB16 — Statistiques KB & recherches infructueuses.

Couvre :
* consulter un article incrémente ``vues`` (distinct de KbLecture) ;
* une recherche ``?search=`` sans résultat est journalisée
  (``KbRechercheVide``), une recherche avec résultat ne l'est PAS ;
* les rapports top/moins consultés et lacunes de connaissance agrègent
  correctement, scopés société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import KbArticle, KbRechercheVide

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


class KbVuesTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-vues', 'V')
        self.user = make_user(self.co, 'kb-vues-user')
        self.article = KbArticle.objects.create(company=self.co, titre='X')

    def test_incrementer_vues_direct(self):
        self.assertEqual(self.article.vues, 0)
        v1 = services.incrementer_vues(self.article)
        self.assertEqual(v1, 1)
        v2 = services.incrementer_vues(self.article)
        self.assertEqual(v2, 2)

    def test_retrieve_increments_vues(self):
        api = auth(self.user)
        api.get(f'{self.ARTICLES}{self.article.id}/')
        api.get(f'{self.ARTICLES}{self.article.id}/')
        self.article.refresh_from_db()
        self.assertEqual(self.article.vues, 2)

    def test_vues_distinct_from_kblecture(self):
        # Consulter deux fois par la MÊME personne compte deux vues, alors que
        # marquer-lu (KbLecture) reste idempotent à une seule ligne.
        services.marquer_lu(self.article, utilisateur=self.user)
        services.marquer_lu(self.article, utilisateur=self.user)
        from apps.kb.models import KbLecture
        self.assertEqual(
            KbLecture.objects.filter(
                article=self.article, utilisateur=self.user).count(), 1)
        services.incrementer_vues(self.article)
        services.incrementer_vues(self.article)
        self.article.refresh_from_db()
        self.assertEqual(self.article.vues, 2)


class KbRechercheVideTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-rv', 'R')
        self.user = make_user(self.co, 'kb-rv-user')
        KbArticle.objects.create(
            company=self.co, titre='Onduleur Huawei', statut='publie')

    def test_empty_search_is_logged(self):
        api = auth(self.user)
        resp = api.get(f'{self.ARTICLES}?search=zorglub-inexistant')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            KbRechercheVide.objects.filter(
                company=self.co, terme='zorglub-inexistant').exists())

    def test_search_with_results_not_logged(self):
        api = auth(self.user)
        resp = api.get(f'{self.ARTICLES}?search=Huawei')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            KbRechercheVide.objects.filter(
                company=self.co, terme='Huawei').exists())

    def test_journaliser_recherche_vide_service(self):
        entry = services.journaliser_recherche_vide(
            self.co, 'terme test', utilisateur=self.user)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.company, self.co)
        self.assertEqual(entry.terme, 'terme test')

    def test_journaliser_ignores_blank_terme(self):
        entry = services.journaliser_recherche_vide(self.co, '   ')
        self.assertIsNone(entry)


class KbRapportsTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-rap', 'RAP')
        self.co_autre = make_company('kb-rap-autre', 'AUTRE')
        self.user = make_user(self.co, 'kb-rap-user')
        self.article_populaire = KbArticle.objects.create(
            company=self.co, titre='Populaire', vues=50)
        self.article_impopulaire = KbArticle.objects.create(
            company=self.co, titre='Impopulaire', vues=1)
        KbArticle.objects.create(
            company=self.co_autre, titre='Autre société', vues=999)

    def test_top_consultes_ordered_desc_and_scoped(self):
        top = selectors.rapport_top_consultes(self.co)
        self.assertEqual(top[0]['id'], self.article_populaire.id)
        ids = {r['id'] for r in top}
        self.assertNotIn(
            KbArticle.objects.get(company=self.co_autre).id, ids)

    def test_moins_consultes_ordered_asc(self):
        moins = selectors.rapport_moins_consultes(self.co)
        self.assertEqual(moins[0]['id'], self.article_impopulaire.id)

    def test_lacunes_connaissance_groups_by_terme_case_insensitive(self):
        KbRechercheVide.objects.create(company=self.co, terme='onduleur hybride')
        KbRechercheVide.objects.create(company=self.co, terme='Onduleur Hybride')
        KbRechercheVide.objects.create(company=self.co, terme='pompe agricole')
        lacunes = selectors.rapport_lacunes_connaissance(self.co)
        top = lacunes[0]
        self.assertEqual(top['terme'], 'onduleur hybride')
        self.assertEqual(top['occurrences'], 2)

    def test_rapports_endpoints(self):
        api = auth(self.user)
        resp1 = api.get(f'{self.ARTICLES}rapport-top-consultes/')
        self.assertEqual(resp1.status_code, 200, resp1.data)
        resp2 = api.get(f'{self.ARTICLES}rapport-moins-consultes/')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        resp3 = api.get(f'{self.ARTICLES}rapport-lacunes-connaissance/')
        self.assertEqual(resp3.status_code, 200, resp3.data)
