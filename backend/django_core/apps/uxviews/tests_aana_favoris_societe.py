"""AANA15 (C-AANA-005) — un favori ne peut viser QUE un enregistrement de la
société de l'appelant, d'un type de la liste blanche.

Scénario U2 : un utilisateur de A épingle ``{modele: 'crm.client',
object_id: <client de B>}``. Avant le correctif : 201, et ``libelle`` = le
nom du client de B (fuite inter-société).

Données RÉELLES en base, vraie résolution contenttypes (aucun mock).
Retirer la vérification rougit ce test.
"""
import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from authentication.models import Company

from .models import FavoriUtilisateur

User = get_user_model()

BASE = '/api/django/uxviews/favoris/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestFavoriSociete(TestCase):
    def setUp(self):
        self.co_a = Company.objects.get_or_create(
            slug='aana15-a', defaults={'nom': 'AANA15 A'})[0]
        self.co_b = Company.objects.get_or_create(
            slug='aana15-b', defaults={'nom': 'AANA15 B'})[0]
        self.user_a = User.objects.create_user(
            username='aana15_a', password='x', company=self.co_a,
            role_legacy='normal')
        self.client_a = Client.objects.create(company=self.co_a, nom='Client A')
        self.client_b = Client.objects.create(
            company=self.co_b, nom='Secret Client B')

    def test_favori_autre_societe_refuse(self):
        api = _api(self.user_a)
        resp = api.post(BASE, {'modele': 'crm.client',
                               'object_id': self.client_b.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertNotIn('Secret Client B', str(resp.data))
        self.assertFalse(FavoriUtilisateur.objects.filter(
            owner=self.user_a, object_id=self.client_b.pk).exists())

        # Un client de A reste favorisable.
        resp = api.post(BASE, {'modele': 'crm.client',
                               'object_id': self.client_a.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['libelle'], str(self.client_a))

    def test_type_hors_liste_blanche_refuse(self):
        resp = _api(self.user_a).post(
            BASE, {'modele': 'authentication.customuser',
                   'object_id': self.user_a.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('modele', resp.data)

    def test_ligne_heritee_ne_fuit_plus(self):
        """Un favori créé AVANT la garde vers une autre société : ni libellé à
        l'écran, ni identifiant dans l'export CSV."""
        ct = ContentType.objects.get_for_model(Client)
        FavoriUtilisateur.objects.create(
            company=self.co_a, owner=self.user_a, content_type=ct,
            object_id=self.client_b.pk)
        api = _api(self.user_a)
        resp = api.get(BASE)
        lignes = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertIsNone(lignes[0]['libelle'])
        resp = api.get(f'{BASE}export-csv/')
        contenu = resp.content.decode('utf-8')
        self.assertNotIn('Secret Client B', contenu)
        export = list(csv.reader(io.StringIO(contenu)))
        self.assertEqual(export[1][1:], ['', '', ''])
