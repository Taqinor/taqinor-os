"""AANA38 — ``?owner=`` n'ouvre plus les vues PERSONNELLES ; le ``libelle``
d'un favori exige le scope de l'entité ciblée.

Constat C-AANA-011 : n'importe quelle clé ``read:vues`` lisait la vue
personnelle d'un collaborateur en posant ``?owner=<son id>`` (un paramètre
n'est pas un consentement) ; et un favori vers un lead publiait le nom du
lead à une clé ``read:favoris`` sans ``read:leads``.

Vraies vues publiques, vraie authentification, vraie base ; rien n'est mocké.

Run :
    python manage.py test apps.publicapi.tests_aana_vues_perso -v2
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from apps.uxviews.models import FavoriUtilisateur, SavedView
from authentication.models import Company

from .models import ApiKey
from .portees import SCOPE_READ_FAVORIS, SCOPE_READ_LEADS, SCOPE_READ_VUES

User = get_user_model()


def _client(brute):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {brute}')
    return api


def _lignes(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class VuesPersonnellesTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana38-co', defaults={'nom': 'AANA38'})
        self.u2 = User.objects.create_user(
            username='aana38-u2', password='x', company=self.co)
        self.perso = SavedView.objects.create(
            company=self.co, owner=self.u2, ecran='crm.leads',
            nom='Perso U2', visibilite=SavedView.Visibilite.PERSONNELLE)
        self.equipe = SavedView.objects.create(
            company=self.co, owner=self.u2, ecran='crm.leads',
            nom='Équipe U2', visibilite=SavedView.Visibilite.EQUIPE)
        _cle, self.brute = ApiKey.issue(
            company=self.co, label='vues', scopes=[SCOPE_READ_VUES])

    def test_owner_ne_debloque_pas(self):
        resp = _client(self.brute).get(
            '/api/public/v1/saved-views/', {'owner': self.u2.id})
        self.assertEqual(resp.status_code, 200)
        noms = {ligne['nom'] for ligne in _lignes(resp)}
        self.assertNotIn('Perso U2', noms)
        self.assertEqual(noms, {'Équipe U2'})

    def test_sans_owner_seulement_l_equipe(self):
        resp = _client(self.brute).get('/api/public/v1/saved-views/')
        self.assertEqual({ligne['nom'] for ligne in _lignes(resp)},
                         {'Équipe U2'})


class LibelleFavoriTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana38-fav', defaults={'nom': 'AANA38 FAV'})
        self.u1 = User.objects.create_user(
            username='aana38-fav-u1', password='x', company=self.co)
        self.lead = Lead.objects.create(company=self.co, nom='Lead secret')
        self.favori = FavoriUtilisateur.objects.create(
            company=self.co, owner=self.u1,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=self.lead.pk)

    def _libelle(self, scopes):
        _cle, brute = ApiKey.issue(company=self.co, label='fav',
                                   scopes=scopes)
        resp = _client(brute).get(
            '/api/public/v1/favoris/', {'owner': self.u1.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = next(ligne for ligne in _lignes(resp)
                     if ligne['id'] == self.favori.id)
        return ligne['libelle']

    def test_libelle_null_sans_le_scope_de_l_entite(self):
        self.assertIsNone(self._libelle([SCOPE_READ_FAVORIS]))

    def test_libelle_publie_avec_le_scope_de_l_entite(self):
        self.assertEqual(
            self._libelle([SCOPE_READ_FAVORIS, SCOPE_READ_LEADS]),
            str(self.lead))
