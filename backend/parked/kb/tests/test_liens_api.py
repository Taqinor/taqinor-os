"""Tests API + sélecteur des liens d'article (``KbArticleLien``).

Couvre : société posée côté serveur (jamais du corps), garde-fou même-société
sur l'``article`` (un lien vers l'article d'une AUTRE société est refusé 400),
isolation de la liste entre sociétés, filtres ``?article=``/``?type_cible=``/
``?cible_id=``, 404 cross-tenant, la recherche INVERSE
``article-liens/articles/?type_cible=&cible_id=`` (scopée société), et le
sélecteur ``liens_enrichis`` — qui ENRICHIT via ``stock.selectors`` pour un
``produit`` existant et DÉGRADE proprement (libellé stocké, ``source='stored'``)
quand l'app cible n'expose pas de sélecteur (``equipement``/``type_intervention``)
ou quand la cible est introuvable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors
from apps.kb.models import KbArticle, KbArticleLien
from apps.stock.models import Produit

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


class KbArticleLienApiTests(TestCase):
    BASE = '/api/django/kb/article-liens/'

    def setUp(self):
        self.co_a = make_company('kb-liens-a', 'A')
        self.co_b = make_company('kb-liens-b', 'B')
        self.user_a = make_user(self.co_a, 'kb-liens-a')
        self.user_b = make_user(self.co_b, 'kb-liens-b')
        self.article_a = KbArticle.objects.create(
            company=self.co_a, titre='Article A')
        self.article_b = KbArticle.objects.create(
            company=self.co_b, titre='Article B')

    def _payload(self, article, **over):
        data = {
            'article': article.id,
            'type_cible': 'equipement',
            'cible_id': 42,
            'libelle': 'Onduleur #42',
        }
        data.update(over)
        return data

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.article_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticleLien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.article, self.article_a)
        self.assertEqual(obj.type_cible, 'equipement')

    def test_create_ignores_company_in_body(self):
        api = auth(self.user_a)
        payload = self._payload(self.article_a, company=self.co_b.id)
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticleLien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_rejects_cross_tenant_article(self):
        # user A tries to link to company B's article -> validation error.
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.article_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('article', resp.data)
        self.assertFalse(KbArticleLien.objects.filter(cible_id=42).exists())

    def test_list_isolation(self):
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='produit', cible_id=7, libelle='P7')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_article_and_type(self):
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='produit', cible_id=7, libelle='P7')
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='equipement', cible_id=8, libelle='E8')
        resp = auth(self.user_a).get(
            self.BASE + '?article=%d&type_cible=equipement' % self.article_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['cible_id'], 8)

    def test_list_filter_by_cible_id(self):
        # Reverse lookup via the list filters: which links target produit #7.
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='produit', cible_id=7, libelle='P7')
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='produit', cible_id=9, libelle='P9')
        resp = auth(self.user_a).get(
            self.BASE + '?type_cible=produit&cible_id=7')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['cible_id'], 7)

    def test_reverse_lookup_articles_action(self):
        # article-liens/articles/?type_cible=produit&cible_id=7 -> linked
        # articles (id/titre/statut), company-scoped.
        a2 = KbArticle.objects.create(company=self.co_a, titre='Article A2')
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='produit', cible_id=7, libelle='P7')
        KbArticleLien.objects.create(
            company=self.co_a, article=a2,
            type_cible='produit', cible_id=7, libelle='P7 bis')
        # B has a link to the same target id but stays isolated.
        KbArticleLien.objects.create(
            company=self.co_b, article=self.article_b,
            type_cible='produit', cible_id=7, libelle='B-P7')
        resp = auth(self.user_a).get(
            self.BASE + 'articles/?type_cible=produit&cible_id=7')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {row['id'] for row in resp.data}
        self.assertEqual(ids, {self.article_a.id, a2.id})
        self.assertIn('titre', resp.data[0])
        self.assertIn('statut', resp.data[0])

    def test_reverse_lookup_requires_params(self):
        resp = auth(self.user_a).get(self.BASE + 'articles/?type_cible=produit')
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_detail_404(self):
        lien = KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible='produit', cible_id=5, libelle='P5')
        resp = auth(self.user_b).get(f'{self.BASE}{lien.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'kb-liens-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class KbArticleLienSelectorTests(TestCase):
    """Le sélecteur d'enrichissement enrichit le produit, dégrade le reste."""

    def setUp(self):
        self.co = make_company('kb-liens-sel', 'S')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Article S')

    def test_enrichment_produit_uses_stock_selector(self):
        # A 'produit' link whose target exists: stock.selectors enriches the
        # libellé to the produit's name (source='live').
        produit = Produit.objects.create(
            company=self.co, nom='Panneau 550W', prix_vente=1000)
        KbArticleLien.objects.create(
            company=self.co, article=self.article,
            type_cible='produit', cible_id=produit.id, libelle='ancien libellé')
        result = selectors.liens_enrichis(self.article)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['type_cible'], 'produit')
        self.assertEqual(row['libelle'], 'Panneau 550W')
        self.assertEqual(row['source'], 'live')

    def test_enrichment_produit_missing_target_degrades(self):
        # A 'produit' link whose target produit does not exist: stock selector
        # is called but returns None -> degrade to stored label, never crash.
        KbArticleLien.objects.create(
            company=self.co, article=self.article,
            type_cible='produit', cible_id=123456, libelle='Produit stocké')
        result = selectors.liens_enrichis(self.article)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['type_cible'], 'produit')
        self.assertEqual(row['libelle'], 'Produit stocké')
        self.assertEqual(row['source'], 'stored')

    def test_enrichment_equipement_and_type_intervention_degrade(self):
        # 'equipement' (sav has no selectors.py) and 'type_intervention' (no
        # target app) -> degrade to stored label, never crash, no import.
        KbArticleLien.objects.create(
            company=self.co, article=self.article,
            type_cible='equipement', cible_id=222222, libelle='Équipement stocké')
        KbArticleLien.objects.create(
            company=self.co, article=self.article,
            type_cible='type_intervention', cible_id=333333,
            libelle='Type stocké')
        result = selectors.liens_enrichis(self.article)
        by_type = {r['type_cible']: r for r in result}
        self.assertEqual(by_type['equipement']['libelle'], 'Équipement stocké')
        self.assertEqual(by_type['equipement']['source'], 'stored')
        self.assertEqual(
            by_type['type_intervention']['libelle'], 'Type stocké')
        self.assertEqual(by_type['type_intervention']['source'], 'stored')

    def test_liens_for_article_is_company_scoped(self):
        KbArticleLien.objects.create(
            company=self.co, article=self.article,
            type_cible='equipement', cible_id=5, libelle='Équipement 5')
        qs = selectors.liens_for_article(self.article)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().cible_id, 5)

    def test_articles_pour_cible_company_scoped(self):
        # Reverse-lookup selector: only this company's articles for the target.
        other = make_company('kb-liens-sel-other', 'O')
        other_article = KbArticle.objects.create(
            company=other, titre='Autre')
        KbArticleLien.objects.create(
            company=self.co, article=self.article,
            type_cible='produit', cible_id=11, libelle='P11')
        KbArticleLien.objects.create(
            company=other, article=other_article,
            type_cible='produit', cible_id=11, libelle='P11-other')
        result = selectors.articles_pour_cible(self.co, 'produit', 11)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], self.article.id)
        self.assertEqual(result[0]['titre'], 'Article S')
