"""Tests XKB18 — Articles multilingues FR/AR.

Couvre :
* créer la version AR d'un article FR les lie (traduction_de) ;
* la bascule de langue fonctionne (l'article traduit porte langue='ar') ;
* modifier le FR (source) marque l'AR (traduction) périmée ;
* mettre à jour la traduction elle-même la remet à jour (non périmée) ;
* isolation cross-tenant (source d'une autre société refusée) ;
* une traduction ne peut pas elle-même être source d'une autre traduction.
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


class KbTraductionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-i18n', 'I')
        self.user = make_user(self.co, 'kb-i18n-u1')
        self.fr = KbArticle.objects.create(
            company=self.co, titre='Procédure', corps='Contenu FR',
            langue='fr', statut=KbArticle.Statut.PUBLIE)

    def test_creer_traduction_links_to_source(self):
        ar = services.creer_traduction(
            self.fr, langue='ar', auteur=self.user, company=self.co)
        self.assertEqual(ar.traduction_de, self.fr)
        self.assertEqual(ar.langue, 'ar')
        self.assertEqual(ar.statut, KbArticle.Statut.BROUILLON)
        self.assertEqual(ar.titre, self.fr.titre)

    def test_source_update_marks_translation_perimee(self):
        ar = services.creer_traduction(
            self.fr, langue='ar', auteur=self.user, company=self.co)
        self.assertFalse(ar.traduction_perimee)
        services.marquer_traductions_perimees(self.fr)
        ar.refresh_from_db()
        self.assertTrue(ar.traduction_perimee)

    def test_updating_translation_itself_does_not_affect_source(self):
        ar = services.creer_traduction(
            self.fr, langue='ar', auteur=self.user, company=self.co)
        services.marquer_traductions_perimees(self.fr)
        ar.refresh_from_db()
        self.assertTrue(ar.traduction_perimee)
        self.fr.refresh_from_db()
        self.assertFalse(self.fr.traduction_perimee)


class KbTraductionApiTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-i18n-api', 'A')
        self.user = make_user(self.co, 'kb-i18n-api-u1')
        self.fr = KbArticle.objects.create(
            company=self.co, titre='Procédure API', corps='Contenu',
            langue='fr')

    def test_traduire_endpoint_creates_linked_article(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.fr.id}/traduire/', {'langue': 'ar'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['langue'], 'ar')
        self.assertEqual(resp.data['traduction_de'], self.fr.id)

    def test_traduire_endpoint_rejects_invalid_langue(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.fr.id}/traduire/', {'langue': 'xx'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_updating_source_marks_translation_stale_via_api(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.fr.id}/traduire/', {'langue': 'ar'},
            format='json')
        ar_id = resp.data['id']

        api = auth(self.user)
        patch_resp = api.patch(
            f'{self.ARTICLES}{self.fr.id}/', {'corps': 'Contenu mis à jour'},
            format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)

        ar = KbArticle.objects.get(id=ar_id)
        self.assertTrue(ar.traduction_perimee)

    def test_updating_translation_clears_its_own_stale_flag(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.fr.id}/traduire/', {'langue': 'ar'},
            format='json')
        ar_id = resp.data['id']
        services.marquer_traductions_perimees(self.fr)
        ar = KbArticle.objects.get(id=ar_id)
        self.assertTrue(ar.traduction_perimee)

        api = auth(self.user)
        patch_resp = api.patch(
            f'{self.ARTICLES}{ar_id}/', {'corps': 'ترجمة محدثة'},
            format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        ar.refresh_from_db()
        self.assertFalse(ar.traduction_perimee)

    def test_cross_tenant_translation_source_rejected(self):
        other_co = make_company('kb-i18n-other', 'O')
        other_article = KbArticle.objects.create(
            company=other_co, titre='Autre', corps='X')
        resp = auth(self.user).patch(
            f'{self.ARTICLES}{self.fr.id}/',
            {'traduction_de': other_article.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_translation_cannot_be_source_of_another_translation(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}{self.fr.id}/traduire/', {'langue': 'ar'},
            format='json')
        ar_id = resp.data['id']
        en = KbArticle.objects.create(company=self.co, titre='EN', corps='X')
        patch_resp = auth(self.user).patch(
            f'{self.ARTICLES}{en.id}/', {'traduction_de': ar_id},
            format='json')
        self.assertEqual(patch_resp.status_code, 400)
