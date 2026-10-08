"""ASTK95 (C-ASTK-026) — créer un fournisseur dont le nom NORMALISÉ (casse,
espaces, accents) existe déjà dans la société renvoie un avertissement NON
bloquant `avertissements.nom` (201 quand même) ; un nom distinct ou un
homonyme d'une autre société n'en déclenche aucun ; l'avertissement n'est
jamais stocké.

Sonde FOUR-20 d'origine : POST « ACME » ×2 → 201/201, aucun avertissement.

Aucun mock : vue et serializer réels.

Run :
    python manage.py test apps.stock.test_astk_fournisseur_doublon_nom -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Fournisseur

User = get_user_model()

URL = '/api/django/stock/fournisseurs/'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DoublonNomTests(TestCase):
    def setUp(self):
        self.co = make_company('astk95-co', 'ASTK95 Co')
        self.autre = make_company('astk95-autre', 'ASTK95 Autre')
        self.admin = User.objects.create_user(
            username='astk95_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = auth(self.admin)
        Fournisseur.objects.create(company=self.co, nom='ACME Énergie')
        Fournisseur.objects.create(company=self.autre, nom='Solaris')

    def test_avertissement_nom_normalise(self):
        rep = self.api.post(URL, {'nom': '  acme   energie '}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertEqual(
            rep.json()['avertissements']['nom'],
            'Un fournisseur « ACME Énergie » existe déjà.')
        self.assertIn('ice', rep.json()['avertissements'])
        # Non bloquant : le fournisseur est créé et relu, sans avertissement
        # stocké.
        cree = Fournisseur.objects.get(pk=rep.json()['id'])
        self.assertEqual(cree.nom, 'acme   energie')
        relu = self.api.get(f'{URL}{cree.pk}/').json()
        self.assertNotIn('avertissements', relu)

    def test_nom_distinct_sans_avertissement(self):
        rep = self.api.post(URL, {'nom': 'Atlas Câbles'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertIsNone(rep.json()['avertissements']['nom'])

    def test_homonyme_autre_societe_ignore(self):
        rep = self.api.post(URL, {'nom': 'SOLARIS'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertIsNone(rep.json()['avertissements']['nom'])

    def test_modifier_soi_meme_sans_avertissement(self):
        existant = Fournisseur.objects.get(company=self.co, nom='ACME Énergie')
        rep = self.api.patch(f'{URL}{existant.pk}/', {'nom': 'Acme Energie'},
                             format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertIsNone(rep.json()['avertissements']['nom'])
