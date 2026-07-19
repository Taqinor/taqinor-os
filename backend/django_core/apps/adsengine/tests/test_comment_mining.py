"""PUB71/PUB72 — Tests de la mine de questions (commentaires) + mine
d'objections (CRM), extraction PURE (regex/mots-clés FR-Darija, JAMAIS un
LLM).

Prouve :
  * ``is_question``/``classify_question_theme`` sont PURES et couvrent les
    marqueurs Darija sans point d'interrogation ;
  * ``mine_comment_questions`` agrège par thème, triée par fréquence, avec
    des candidats ``seed_brief`` prêts à l'emploi ;
  * ``classify_objection_theme`` (prix/confiance/délai/technique) ;
  * ``mine_ad_objections`` résout PAR AD via la même échelle que
    ``attribution.variant_attribution`` (ADSENG6), groupe les leads sans clé
    d'ad en « non résolues », et suggère un angle par thème (backlog, jamais
    une action) ;
  * les deux endpoints reporting sont gatés ``adsengine_view``.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.crm.stages import COLD
from apps.roles.models import Role

from apps.adsengine import comment_mining
from apps.adsengine.models import AdMirror, CommentMirror

User = get_user_model()
FAQ_URL = '/api/django/adsengine/reporting/creatifs/faq/'
OBJECTIONS_URL = '/api/django/adsengine/reporting/creatifs/objections/'


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


# ── PUB72 — extraction PURE (objections CRM) ─────────────────────────────────
class ClassifyObjectionThemeTests(SimpleTestCase):
    def test_prix(self):
        self.assertEqual(
            comment_mining.classify_objection_theme('Trop cher pour moi'),
            comment_mining.OBJECTION_PRIX)

    def test_confiance(self):
        self.assertEqual(
            comment_mining.classify_objection_theme(
                'Il doute de la fiabilité de l\'entreprise'),
            comment_mining.OBJECTION_CONFIANCE)

    def test_delai(self):
        self.assertEqual(
            comment_mining.classify_objection_theme('Trop de retard annoncé'),
            comment_mining.OBJECTION_DELAI)

    def test_technique(self):
        self.assertEqual(
            comment_mining.classify_objection_theme(
                'Problème technique lors de l\'installation'),
            comment_mining.OBJECTION_TECHNIQUE)

    def test_empty_returns_none(self):
        self.assertIsNone(comment_mining.classify_objection_theme(''))

    def test_unknown_keyword_is_autre(self):
        self.assertEqual(
            comment_mining.classify_objection_theme('Ne répond plus'),
            comment_mining.OBJECTION_AUTRE)


class MineAdObjectionsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Obj Co', slug='obj-co')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_1', name='Reel Solaire')

    def _lead(self, **fields):
        return Lead.objects.create(
            company=self.company, nom='Prospect', stage=COLD, **fields)

    def _note(self, lead, body):
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.NOTE,
            body=body)

    def test_objections_resolved_per_ad_with_angle(self):
        lead = self._lead(meta_ad_id='ad_1', motif_perte='Trop cher pour lui')
        self._note(lead, 'Client hésite, dit que le prix est trop élevé')

        data = comment_mining.mine_ad_objections(self.company)
        self.assertEqual(len(data['par_ad']), 1)
        row = data['par_ad'][0]
        self.assertEqual(row['meta_id'], 'ad_1')
        self.assertEqual(row['objections'][0]['theme'],
                         comment_mining.OBJECTION_PRIX)
        # 2 mentions de prix (motif_perte + note).
        self.assertEqual(row['objections'][0]['count'], 2)
        self.assertIn(
            comment_mining._SUGGESTED_ANGLES_FR[comment_mining.OBJECTION_PRIX],
            row['angles_suggeres'])

    def test_lead_without_ad_key_goes_unresolved(self):
        lead = self._lead(canal=Lead.Canal.WHATSAPP_CTWA)
        self._note(lead, 'Il n\'a pas confiance dans le sérieux du projet')
        data = comment_mining.mine_ad_objections(self.company)
        self.assertEqual(data['par_ad'], [])
        self.assertEqual(
            data['non_resolues']['objections'][0]['theme'],
            comment_mining.OBJECTION_CONFIANCE)

    def test_lead_without_text_ignored(self):
        self._lead(meta_ad_id='ad_1')
        data = comment_mining.mine_ad_objections(self.company)
        self.assertEqual(data['par_ad'], [])
        self.assertEqual(data['non_resolues']['objections'], [])

    def test_structured_activity_kinds_never_mined(self):
        lead = self._lead(meta_ad_id='ad_1')
        # Une entrée MODIFICATION (log structuré, jamais une objection) —
        # jamais minée, même si son texte contient un mot-clé.
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', old_value='new', new_value='trop cher')
        data = comment_mining.mine_ad_objections(self.company)
        self.assertEqual(data['par_ad'], [])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Obj', slug='other-obj')
        other_lead = Lead.objects.create(
            company=other, nom='X', stage=COLD, meta_ad_id='ad_1')
        LeadActivity.objects.create(
            company=other, lead=other_lead, kind=LeadActivity.Kind.NOTE,
            body='Trop cher pour lui')
        data = comment_mining.mine_ad_objections(self.company)
        self.assertEqual(data['par_ad'], [])


class AdObjectionsEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ObjEp Co', slug='objep-co')
        self.viewer = make_user(self.company, 'obj-viewer', ['adsengine_view'])

    def test_endpoint_returns_shape(self):
        resp = auth(self.viewer).get(OBJECTIONS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('par_ad', resp.data)
        self.assertIn('non_resolues', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'obj-nobody', [])
        self.assertEqual(auth(nobody).get(OBJECTIONS_URL).status_code, 403)
