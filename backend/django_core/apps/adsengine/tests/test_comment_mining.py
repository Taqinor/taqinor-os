"""PUB71 — Tests de la mine de questions des commentaires, extraction PURE
(regex/mots-clés FR-Darija, JAMAIS un LLM).

Prouve :
  * ``is_question``/``classify_question_theme`` sont PURES et couvrent les
    marqueurs Darija sans point d'interrogation ;
  * ``mine_comment_questions`` agrège par thème, triée par fréquence, avec
    des candidats ``seed_brief`` prêts à l'emploi ;
  * l'endpoint reporting est gaté ``adsengine_view``.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import comment_mining
from apps.adsengine.models import CommentMirror

User = get_user_model()
FAQ_URL = '/api/django/adsengine/reporting/creatifs/faq/'


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


class IsQuestionPureTests(SimpleTestCase):
    def test_question_mark_detected(self):
        self.assertTrue(comment_mining.is_question('Quel est le prix ?'))

    def test_darija_marker_without_question_mark(self):
        self.assertTrue(comment_mining.is_question('chhal ta7ssb had panneau'))

    def test_statement_is_not_a_question(self):
        self.assertFalse(comment_mining.is_question('Superbe installation !'))

    def test_empty_text_is_not_a_question(self):
        self.assertFalse(comment_mining.is_question(''))
        self.assertFalse(comment_mining.is_question(None))


class ClassifyQuestionThemeTests(SimpleTestCase):
    def test_prix_theme(self):
        self.assertEqual(
            comment_mining.classify_question_theme('C\'est combien le prix ?'),
            comment_mining.THEME_PRIX)

    def test_garantie_theme(self):
        self.assertEqual(
            comment_mining.classify_question_theme('Quelle garantie svp ?'),
            comment_mining.THEME_GARANTIE)

    def test_subvention_theme(self):
        self.assertEqual(
            comment_mining.classify_question_theme(
                'Il y a une subvention disponible ?'),
            comment_mining.THEME_SUBVENTION)

    def test_duree_theme(self):
        self.assertEqual(
            comment_mining.classify_question_theme(
                'Le délai d\'installation est encore long ?'),
            comment_mining.THEME_DUREE)

    def test_first_matching_theme_wins_deterministically(self):
        # 'combien' (prix) et 'délai' (durée) coexistent — prix est vérifié en
        # premier (ordre du dict _THEME_KEYWORDS), déterministe, jamais un LLM.
        self.assertEqual(
            comment_mining.classify_question_theme(
                'Le délai est de combien de temps ?'),
            comment_mining.THEME_PRIX)

    def test_non_question_returns_none(self):
        self.assertIsNone(
            comment_mining.classify_question_theme('Merci pour la visite.'))

    def test_question_without_known_keyword_is_autre(self):
        self.assertEqual(
            comment_mining.classify_question_theme('Vous êtes ouverts ?'),
            comment_mining.THEME_AUTRE)


class MineCommentQuestionsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Mine Co', slug='mine-co')

    def _comment(self, message, meta_id):
        return CommentMirror.objects.create(
            company=self.company, meta_id=meta_id, message=message,
            created_time=timezone.now())

    def test_aggregates_by_theme_sorted_by_frequency(self):
        self._comment('Combien coûte le kit ?', 'c1')
        self._comment('Quel est le prix exact ?', 'c2')
        self._comment('Quelle garantie sur les panneaux ?', 'c3')
        self._comment('Bravo pour le travail !', 'c4')  # pas une question

        data = comment_mining.mine_comment_questions(self.company)
        self.assertEqual(data['total_comments'], 4)
        self.assertEqual(data['total_questions'], 3)
        self.assertEqual(data['themes'][0]['theme'], comment_mining.THEME_PRIX)
        self.assertEqual(data['themes'][0]['count'], 2)
        self.assertEqual(len(data['seed_brief_candidates']), 2)

    def test_no_comments_gives_empty_report(self):
        data = comment_mining.mine_comment_questions(self.company)
        self.assertEqual(data['themes'], [])
        self.assertEqual(data['seed_brief_candidates'], [])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Mine', slug='other-mine')
        CommentMirror.objects.create(
            company=other, meta_id='oc1', message='Combien ça coûte ?',
            created_time=timezone.now())
        data = comment_mining.mine_comment_questions(self.company)
        self.assertEqual(data['total_comments'], 0)


class CommentFaqEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Faq Co', slug='faq-co')
        self.viewer = make_user(self.company, 'faq-viewer', ['adsengine_view'])

    def test_endpoint_returns_faq_shape(self):
        CommentMirror.objects.create(
            company=self.company, meta_id='c1', message='Combien ça coûte ?',
            created_time=timezone.now())
        resp = auth(self.viewer).get(FAQ_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('themes', resp.data)
        self.assertIn('seed_brief_candidates', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'faq-nobody', [])
        self.assertEqual(auth(nobody).get(FAQ_URL).status_code, 403)
