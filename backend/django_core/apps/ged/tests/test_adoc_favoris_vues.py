"""ADOC15 — favoris limités aux documents visibles ; vue partagée modifiable
par son créateur ou un gestionnaire seulement.

Rejoue les sondes #32/#33 de l'audit documents (2026-10-05) : un favori mis
en corbeille restait listé (alors que GET /documents/<id>/ = 404) ; un
collègue renommait une vue partagée (PATCH 200).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, Coffre, Document, FavoriGed, Folder, VueGedEnregistree,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FavorisVuesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc15', defaults={'nom': 'ADOC15'})[0]
        self.admin = User.objects.create_user(
            username='adoc15-admin', password='x', company=self.co,
            role_legacy='admin')
        self.u = User.objects.create_user(
            username='adoc15-u', password='x', company=self.co,
            role_legacy='normal')
        self.autre = User.objects.create_user(
            username='adoc15-autre', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')

    def _ids_favoris(self):
        resp = auth(self.u).get(f'{BASE}mes-favoris/')
        self.assertEqual(resp.status_code, 200)
        return [d['id'] for d in resp.data['documents']]

    def test_favori_corbeille_masque(self):
        d = Document.objects.create(company=self.co, folder=self.folder,
                                    nom='D')
        f = Document.objects.create(company=self.co, folder=self.folder,
                                    nom='F')
        for doc in (d, f):
            FavoriGed.objects.create(company=self.co, utilisateur=self.u,
                                     document=doc)
        self.assertEqual(sorted(self._ids_favoris()), sorted([d.pk, f.pk]))
        services.mettre_en_corbeille(d, self.admin)
        coffre = Coffre.objects.create(
            company=self.co, nom='Coffre autre', proprietaire=self.autre)
        Document.objects.filter(pk=f.pk).update(coffre=coffre)
        self.assertEqual(self._ids_favoris(), [])
        self.assertEqual(FavoriGed.objects.filter(utilisateur=self.u).count(), 2)
        services.restaurer_de_corbeille(d)
        self.assertEqual(self._ids_favoris(), [d.pk])

    def test_vue_partagee_patch_403(self):
        vue = VueGedEnregistree.objects.create(
            company=self.co, utilisateur=self.autre, nom='Ma vue',
            partagee=True)
        resp = auth(self.u).patch(f'{BASE}vues/{vue.pk}/',
                                  {'nom': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        vue.refresh_from_db()
        self.assertEqual(vue.nom, 'Ma vue')
        self.assertTrue(vue.partagee)
        resp = auth(self.autre).patch(f'{BASE}vues/{vue.pk}/',
                                      {'nom': 'Renommée'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        vue.refresh_from_db()
        self.assertEqual(vue.nom, 'Renommée')
