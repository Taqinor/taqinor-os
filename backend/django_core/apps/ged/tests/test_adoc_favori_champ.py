"""ADOC35 — DocumentSerializer expose `favori` pour l'utilisateur de la requête.

Constat C-ADOC-025 de l'audit documents (2026-10-05) : aucune clé `favori`
→ l'étoile du panneau Détails s'ouvrait vide pour un document favori.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged.models import Cabinet, Document, FavoriGed, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/documents/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FavoriChampTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc35', defaults={'nom': 'ADOC35'})[0]
        self.u = User.objects.create_user(
            username='adoc35-u', password='x', company=self.co,
            role_legacy='normal')
        self.autre = User.objects.create_user(
            username='adoc35-autre', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        self.doc = Document.objects.create(company=self.co, folder=folder,
                                           nom='D')

    def test_document_porte_favori(self):
        FavoriGed.objects.create(company=self.co, utilisateur=self.u,
                                 document=self.doc)
        resp = auth(self.u).get(f'{BASE}{self.doc.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.data['favori'], True)
        # Personnel : le collègue ne le voit pas en favori.
        resp = auth(self.autre).get(f'{BASE}{self.doc.pk}/')
        self.assertIs(resp.data['favori'], False)
        # Toggle : le premier clic retire le favori, relu ensuite.
        toggle = auth(self.u).post(f'{BASE}{self.doc.pk}/favori/')
        self.assertEqual(toggle.status_code, 200, toggle.content)
        self.assertIs(toggle.data['favori'], False)
        resp = auth(self.u).get(f'{BASE}{self.doc.pk}/')
        self.assertIs(resp.data['favori'], False)
        liste = auth(self.u).get(BASE)
        lignes = liste.data['results'] if isinstance(liste.data, dict) \
            and 'results' in liste.data else liste.data
        self.assertIs(next(d for d in lignes if d['id'] == self.doc.pk)['favori'],
                      False)
