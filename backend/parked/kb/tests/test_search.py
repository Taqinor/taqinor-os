"""Tests KB3 — recherche plein-texte + filtres catégorie/tag/statut.

Couvre : recherche ``?search=`` sur titre ET contenu, filtres ``?categorie=`` /
``?tag=`` / ``?statut=``, combinaison recherche+filtre, comportement requête
vide (renvoie tout), et l'invariant multi-société (un résultat ne fuit JAMAIS
d'une société à l'autre, recherche/filtre inclus).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

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


def titres(resp):
    return sorted(r['titre'] for r in rows(resp))


class KbSearchTests(TestCase):
    BASE = '/api/django/kb/articles/'

    def setUp(self):
        self.co_a = make_company('kbs-a', 'A')
        self.co_b = make_company('kbs-b', 'B')
        self.user_a = make_user(self.co_a, 'kbs-a')
        self.user_b = make_user(self.co_b, 'kbs-b')

        # Société A : trois articles couvrant catégorie/tags/statut variés.
        self.onduleur = KbArticle.objects.create(
            company=self.co_a, titre='Onduleur hybride',
            corps='Procédure de mise en service onduleur.',
            categorie='technique', tags='onduleur,sav',
            statut=KbArticle.Statut.PUBLIE)
        self.batterie = KbArticle.objects.create(
            company=self.co_a, titre='Entretien batterie',
            corps='Contrôle annuel de la batterie lithium.',
            categorie='maintenance', tags='batterie,sav',
            statut=KbArticle.Statut.BROUILLON)
        self.facturation = KbArticle.objects.create(
            company=self.co_a, titre='Process facturation',
            corps='Onduleur cité ici dans le corps uniquement.',
            categorie='administratif', tags='compta',
            statut=KbArticle.Statut.PUBLIE)

        # Société B : un article qui matcherait chaque requête de A — il ne doit
        # JAMAIS apparaître dans les résultats de A.
        KbArticle.objects.create(
            company=self.co_b, titre='Onduleur B',
            corps='Onduleur côté société B.',
            categorie='technique', tags='onduleur,sav',
            statut=KbArticle.Statut.PUBLIE)

    # --- recherche plein-texte -------------------------------------------
    def test_search_matches_titre(self):
        resp = auth(self.user_a).get(self.BASE, {'search': 'batterie'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Entretien batterie'])

    def test_search_matches_corps(self):
        # "facturation" n'est pas dans le titre "Process facturation"? il l'est.
        # On cherche un mot présent UNIQUEMENT dans le corps d'un article.
        resp = auth(self.user_a).get(self.BASE, {'search': 'lithium'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Entretien batterie'])

    def test_search_spans_titre_and_corps(self):
        # "onduleur" est dans le titre de l'un et dans le corps d'un autre.
        resp = auth(self.user_a).get(self.BASE, {'search': 'onduleur'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            titres(resp), ['Onduleur hybride', 'Process facturation'])

    def test_search_is_case_insensitive(self):
        resp = auth(self.user_a).get(self.BASE, {'search': 'BATTERIE'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Entretien batterie'])

    def test_empty_search_returns_all(self):
        resp = auth(self.user_a).get(self.BASE, {'search': ''})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 3)

    def test_no_query_returns_all(self):
        resp = auth(self.user_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 3)

    # --- filtres ----------------------------------------------------------
    def test_filter_categorie(self):
        resp = auth(self.user_a).get(self.BASE, {'categorie': 'maintenance'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Entretien batterie'])

    def test_filter_categorie_case_insensitive(self):
        resp = auth(self.user_a).get(self.BASE, {'categorie': 'Technique'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Onduleur hybride'])

    def test_filter_tag(self):
        resp = auth(self.user_a).get(self.BASE, {'tag': 'sav'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            titres(resp), ['Entretien batterie', 'Onduleur hybride'])

    def test_filter_statut(self):
        resp = auth(self.user_a).get(
            self.BASE, {'statut': KbArticle.Statut.PUBLIE})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            titres(resp), ['Onduleur hybride', 'Process facturation'])

    def test_filter_unknown_categorie_returns_empty(self):
        resp = auth(self.user_a).get(self.BASE, {'categorie': 'inexistante'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 0)

    def test_search_and_filter_combined(self):
        # "sav" couvre deux articles ; restreint au statut publié → un seul.
        resp = auth(self.user_a).get(
            self.BASE, {'tag': 'sav', 'statut': KbArticle.Statut.PUBLIE})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Onduleur hybride'])

    # --- isolation multi-société -----------------------------------------
    def test_search_never_leaks_across_companies(self):
        # B cherche un terme présent chez A ET chez B : ne voit que le sien.
        resp = auth(self.user_b).get(self.BASE, {'search': 'onduleur'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Onduleur B'])

    def test_filter_never_leaks_across_companies(self):
        # B filtre sur une catégorie présente chez A ET chez B.
        resp = auth(self.user_b).get(self.BASE, {'categorie': 'technique'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Onduleur B'])

    def test_filter_tag_never_leaks_across_companies(self):
        resp = auth(self.user_b).get(self.BASE, {'tag': 'sav'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(titres(resp), ['Onduleur B'])
