"""NTUX33 — endpoints API publique LECTURE SEULE pour favoris et vues
sauvegardées (apps.uxviews), sous /api/public/v1/. Couvre : scope requis,
isolation multi-société, refus explicite des favoris sans `?owner=`
(consentement), vues d'équipe visibles sans `?owner=`, vues personnelles
d'un tiers jamais fuitées sans son `?owner=`.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.uxviews.models import FavoriUtilisateur, SavedView

from .constants import SCOPE_READ_FAVORIS, SCOPE_READ_LEADS, SCOPE_READ_VUES
from .models import ApiKey

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class PublicSavedViewReadOnlyTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pa-ux33-a', 'PA UX33 A')
        self.co_b = make_company('pa-ux33-b', 'PA UX33 B')
        self.user_a1 = User.objects.create_user(
            username='pa-ux33-a1', password='x', company=self.co_a)
        self.user_a2 = User.objects.create_user(
            username='pa-ux33-a2', password='x', company=self.co_a)
        self.key_a, self.raw_a = ApiKey.issue(
            company=self.co_a, label='A', scopes=[SCOPE_READ_VUES])
        self.equipe_a = SavedView.objects.create(
            company=self.co_a, owner=self.user_a1, ecran='crm.leads',
            nom='Équipe A', visibilite=SavedView.Visibilite.EQUIPE)
        self.perso_a1 = SavedView.objects.create(
            company=self.co_a, owner=self.user_a1, ecran='crm.leads',
            nom='Perso A1', visibilite=SavedView.Visibilite.PERSONNELLE)
        self.perso_a2 = SavedView.objects.create(
            company=self.co_a, owner=self.user_a2, ecran='crm.leads',
            nom='Perso A2', visibilite=SavedView.Visibilite.PERSONNELLE)
        self.equipe_b = SavedView.objects.create(
            company=self.co_b, owner=self.user_a1, ecran='crm.leads',
            nom='Équipe B (autre société)', visibilite=SavedView.Visibilite.EQUIPE)

    def test_requires_scope(self):
        key_no_scope, raw = ApiKey.issue(
            company=self.co_a, label='sans scope', scopes=[SCOPE_READ_LEADS])
        resp = key_client(raw).get('/api/public/v1/saved-views/')
        self.assertEqual(resp.status_code, 403)

    def test_without_owner_only_team_shared_views_are_returned(self):
        resp = key_client(self.raw_a).get('/api/public/v1/saved-views/')
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = {r['nom'] for r in rows(resp)}
        self.assertEqual(noms, {'Équipe A'})

    def test_with_owner_returns_only_that_owners_rows(self):
        resp = key_client(self.raw_a).get(
            '/api/public/v1/saved-views/', {'owner': self.user_a1.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = {r['nom'] for r in rows(resp)}
        # Ses propres vues (personnelle + équipe qu'il possède), jamais celle
        # de user_a2.
        self.assertEqual(noms, {'Équipe A', 'Perso A1'})

    def test_owner_never_leaks_another_users_personal_view(self):
        resp = key_client(self.raw_a).get(
            '/api/public/v1/saved-views/', {'owner': self.user_a2.id})
        noms = {r['nom'] for r in rows(resp)}
        self.assertEqual(noms, {'Perso A2'})
        self.assertNotIn('Perso A1', noms)

    def test_cross_tenant_isolation(self):
        # La clé de la société A ne voit jamais les vues de la société B,
        # même partagées à l'équipe.
        resp = key_client(self.raw_a).get('/api/public/v1/saved-views/')
        noms = {r['nom'] for r in rows(resp)}
        self.assertNotIn('Équipe B (autre société)', noms)


class PublicFavoriReadOnlyTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pa-ux33-fav-a', 'PA UX33 FAV A')
        self.co_b = make_company('pa-ux33-fav-b', 'PA UX33 FAV B')
        self.user_a1 = User.objects.create_user(
            username='pa-ux33-fav-a1', password='x', company=self.co_a)
        self.user_a2 = User.objects.create_user(
            username='pa-ux33-fav-a2', password='x', company=self.co_a)
        self.key_a, self.raw_a = ApiKey.issue(
            company=self.co_a, label='A', scopes=[SCOPE_READ_FAVORIS])
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(SavedView)
        self.favori_a1 = FavoriUtilisateur.objects.create(
            company=self.co_a, owner=self.user_a1, content_type=ct, object_id=1)
        self.favori_a2 = FavoriUtilisateur.objects.create(
            company=self.co_a, owner=self.user_a2, content_type=ct, object_id=2)

    def test_missing_owner_is_rejected_explicitly(self):
        # NTAPI3 — enveloppe d'erreur Stripe-like : le champ fautif remonte
        # dans `error.param`.
        resp = key_client(self.raw_a).get('/api/public/v1/favoris/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error']['param'], 'owner')

    def test_owner_returns_only_their_own_favoris(self):
        resp = key_client(self.raw_a).get(
            '/api/public/v1/favoris/', {'owner': self.user_a1.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [self.favori_a1.id])

    def test_owner_never_leaks_a_colleagues_favori(self):
        resp = key_client(self.raw_a).get(
            '/api/public/v1/favoris/', {'owner': self.user_a1.id})
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.favori_a2.id, ids)

    def test_company_a_key_never_returns_a_company_b_owner_id_collision(self):
        # Un id d'utilisateur inexistant côté A (même si valide côté B) ne
        # renvoie jamais rien — le scoping société protège même sans
        # validation explicite du propriétaire.
        user_b = User.objects.create_user(
            username='pa-ux33-fav-b1', password='x', company=self.co_b)
        resp = key_client(self.raw_a).get(
            '/api/public/v1/favoris/', {'owner': user_b.id})
        self.assertEqual(rows(resp), [])
