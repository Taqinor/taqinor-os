"""AUD526 — ``suggestions_portail`` recoupe enfin ``visible_portail`` et
``visibilite``.

Constat d'audit (le ROUGE figé ici) : le sélecteur ne filtrait que
``statut=PUBLIE`` + ``visible_portail=True``, sans jamais regarder
``visibilite`` (l'ACL de section XKB9). Un article publié sur le portail puis
repassé en ``prive`` (notes personnelles) restait servi — titre + 500
caractères de corps — à tout appelant du sélecteur, et le serializer
n'opposait aucune validation croisée (``visible_portail`` était un simple
booléen inscriptible).

Deux barrières désormais :
  * serializer — publier explicitement un article non-``workspace`` est refusé,
    et le repasser en ``prive`` remet ``visible_portail`` à False ;
  * sélecteur — ``visibilite=WORKSPACE`` exigé (défense en profondeur pour les
    lignes déjà en base).

Run :
    python manage.py test apps.kb.tests.test_aud526_portail_visibilite -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.kb.models import KbArticle
from apps.kb.selectors import suggestions_portail

User = get_user_model()

BASE = '/api/django/kb/articles/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AUD526PortailVisibiliteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='kb-aud526', defaults={'nom': 'KB AUD526'})
        self.user = User.objects.create_user(
            username='kb-aud526', password='x', company=self.company,
            role_legacy='responsable')
        self.api = auth(self.user)

    def _article(self, **extra):
        params = dict(
            company=self.company, titre='Onduleur en défaut',
            corps='Vérifiez le code erreur E07.',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        params.update(extra)
        return KbArticle.objects.create(**params)

    # ── Sélecteur : défense en profondeur ───────────────────────────────────

    def test_article_prive_exclu_des_suggestions(self):
        """Le ROUGE : un article privé (mais visible_portail=True en base)
        était servi au portail."""
        self._article(visibilite=KbArticle.Visibilite.PRIVE)
        self.assertEqual(suggestions_portail(self.company, 'onduleur'), [])

    def test_article_partage_exclu_des_suggestions(self):
        self._article(visibilite=KbArticle.Visibilite.PARTAGE)
        self.assertEqual(suggestions_portail(self.company, 'onduleur'), [])

    def test_article_workspace_toujours_servi(self):
        """Non-régression XSAV22 : le cas normal reste inchangé."""
        article = self._article(visibilite=KbArticle.Visibilite.WORKSPACE)
        suggestions = suggestions_portail(self.company, 'onduleur')
        self.assertEqual([s['id'] for s in suggestions], [article.id])

    # ── Serializer : validation croisée ─────────────────────────────────────

    def test_publier_un_article_prive_sur_le_portail_refuse(self):
        resp = self.api.post(BASE, {
            'titre': 'Notes perso', 'corps': 'Brouillon',
            'visibilite': KbArticle.Visibilite.PRIVE,
            'visible_portail': True,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('visible_portail', resp.data)

    def test_repasser_en_prive_retire_du_portail(self):
        article = self._article(visibilite=KbArticle.Visibilite.WORKSPACE)
        resp = self.api.patch(f'{BASE}{article.id}/', {
            'visibilite': KbArticle.Visibilite.PRIVE,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        article.refresh_from_db()
        self.assertEqual(article.visibilite, KbArticle.Visibilite.PRIVE)
        self.assertFalse(article.visible_portail)
        self.assertEqual(suggestions_portail(self.company, 'onduleur'), [])

    def test_publication_portail_workspace_inchangee(self):
        article = self._article(
            visibilite=KbArticle.Visibilite.WORKSPACE, visible_portail=False)
        resp = self.api.patch(f'{BASE}{article.id}/', {
            'visible_portail': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        article.refresh_from_db()
        self.assertTrue(article.visible_portail)
