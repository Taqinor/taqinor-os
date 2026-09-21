"""Tests dédiés FeedbackProduit (NTIDE58).

Couvre, du critère d'acceptation, les items satisfiables sur l'état ACTUEL
du modèle (``FeedbackProduit`` — NTIDE36/37/38) : création refusée sans
authentification / acceptée avec, liste réservée au palier admin,
agrégation par thème (déjà couverte en détail par ``test_ntide38_feedback_
resume.py`` — ici : vérification bout-en-bout qu'une création POST alimente
bien l'agrégation lue par l'admin).

Les 3 sous-items restants — « sentiment flag » (``FeedbackProduit.sentiment``,
NTIDE42), « context link » (``context_type``/``context_id``, NTIDE43) et
« modération masquage » (action ``masquer``, NTIDE47) — étaient bloqués tant
que ces champs n'existaient pas ; NTIDE42/43/47 étant maintenant sur
``main``, ils sont couverts ci-dessous (les cas unitaires détaillés restent
dans ``test_ntide42_sentiment.py``/``test_ntide43_feedback_context.py``/
``test_ntide47_feedback_moderation.py``, non dupliqués : ici la vérification
bout-en-bout du parcours de création/consultation demandé par NTIDE58).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FeedbackProduitCreateTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide58-a', 'A')
        self.user_a = make_user(self.co_a, 'ntide58-user')

    def _payload(self):
        return {'titre': 'Un retour', 'description': 'Détail',
                'theme': FeedbackProduit.Theme.UX}

    def test_create_unauthenticated_rejected(self):
        resp = APIClient().post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(FeedbackProduit.objects.count(), 0)

    def test_create_authenticated_accepted(self):
        resp = auth(self.user_a).post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = FeedbackProduit.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.auteur, self.user_a)


class FeedbackProduitListAdminOnlyTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide58-list-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide58-list-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'ntide58-list-normal')
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal_a, titre='Retour')

    def test_admin_can_list(self):
        resp = auth(self.admin_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)

    def test_normal_role_refused_on_list(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class FeedbackProduitThemeAggregationEndToEndTests(TestCase):
    """Bout-en-bout : une création POST par un utilisateur normal alimente
    bien l'agrégation ``feedback_by_theme`` lue par l'admin (les cas
    unitaires du sélecteur restent dans ``test_ntide38_feedback_resume.py``,
    non dupliqués ici)."""

    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide58-agg-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide58-agg-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'ntide58-agg-normal')

    def test_created_feedback_appears_in_theme_aggregation(self):
        auth(self.normal_a).post(
            self.BASE,
            {'titre': 'Bug écran devis', 'theme': FeedbackProduit.Theme.BUG},
            format='json')
        resume = selectors.feedback_by_theme(self.co_a)
        bug = next(r for r in resume if r['theme'] == 'bug')
        self.assertEqual(bug['total'], 1)
        self.assertEqual(bug['non_lus'], 1)
        self.assertIn('Bug écran devis', bug['exemples'])


class FeedbackProduitSentimentContexteModerationTests(TestCase):
    """Les 3 sous-items NTIDE58 restants, débloqués par NTIDE42/43/47 :
    drapeau de sentiment, lien de contexte opaque, masquage de modération."""

    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide58-scm-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide58-scm-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'ntide58-scm-normal')

    # ── sentiment flag (NTIDE42) ────────────────────────────────────────────
    def test_sentiment_written_at_creation_and_optional(self):
        resp = auth(self.normal_a).post(self.BASE, {
            'titre': "Ça m'énerve", 'theme': FeedbackProduit.Theme.UX,
            'sentiment': FeedbackProduit.Sentiment.NEGATIF,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            FeedbackProduit.objects.get(id=resp.data['id']).sentiment,
            FeedbackProduit.Sentiment.NEGATIF)
        # Optionnel : jamais imposé au formulaire (NTIDE37).
        sans = auth(self.normal_a).post(
            self.BASE, {'titre': 'Sans sentiment'}, format='json')
        self.assertEqual(sans.status_code, 201, sans.data)
        self.assertEqual(
            FeedbackProduit.objects.get(id=sans.data['id']).sentiment, '')

    def test_sentiment_visible_in_theme_aggregation(self):
        auth(self.normal_a).post(self.BASE, {
            'titre': "J'adore", 'theme': FeedbackProduit.Theme.UX,
            'sentiment': FeedbackProduit.Sentiment.POSITIF,
        }, format='json')
        resume = selectors.feedback_by_theme(self.co_a)
        ux = next(r for r in resume if r['theme'] == 'ux')
        self.assertEqual(ux['par_sentiment'],
                         {FeedbackProduit.Sentiment.POSITIF: 1})

    # ── context link (NTIDE43) ──────────────────────────────────────────────
    def test_context_link_stored_and_returned_to_admin(self):
        resp = auth(self.normal_a).post(self.BASE, {
            'titre': 'Feedback sur un devis',
            'context_type': 'devis', 'context_id': 123,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = FeedbackProduit.objects.get(id=resp.data['id'])
        self.assertEqual(obj.context_type, 'devis')
        self.assertEqual(obj.context_id, 123)
        detail = auth(self.admin_a).get(f'{self.BASE}{obj.id}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['context_type'], 'devis')
        self.assertEqual(detail.data['context_id'], 123)

    # ── modération masquage (NTIDE47) ───────────────────────────────────────
    def test_masquage_hides_without_deleting(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal_a, titre='Inapproprié')
        resp = auth(self.admin_a).post(f'{self.BASE}{fb.id}/masquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        fb.refresh_from_db()
        self.assertTrue(fb.archived)
        self.assertTrue(FeedbackProduit.objects.filter(id=fb.id).exists())
        liste = auth(self.admin_a).get(self.BASE)
        self.assertEqual(len(liste.data['results']), 0)
