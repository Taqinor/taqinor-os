"""Tests ZGED12 — Presse-papiers Knowledge (blocs de texte réutilisables).

Couvre :
* créer un bloc « Signature standard » (personnel) ;
* les blocs SOCIÉTÉ sont partagés (visibles de tous), les PERSONNELS restent
  privés (visibles du seul créateur, sauf admin) ;
* suppression réservée au créateur/admin ;
* isolation cross-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors
from apps.kb.models import BlocReutilisable

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


class BlocReutilisableSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-bloc', 'B')
        self.admin = make_user(self.co, 'kb-bloc-admin', role='admin')
        self.user1 = make_user(self.co, 'kb-bloc-u1')
        self.user2 = make_user(self.co, 'kb-bloc-u2')
        self.bloc_societe = BlocReutilisable.objects.create(
            company=self.co, nom='Signature standard', corps='Cordialement,',
            portee=BlocReutilisable.Portee.SOCIETE, created_by=self.user1)
        self.bloc_perso = BlocReutilisable.objects.create(
            company=self.co, nom='Note perso', corps='Brouillon',
            portee=BlocReutilisable.Portee.PERSONNEL, created_by=self.user1)

    def test_societe_bloc_visible_by_everyone(self):
        visibles = selectors.blocs_visibles(self.co, self.user2)
        self.assertIn(self.bloc_societe, visibles)

    def test_personnel_bloc_not_visible_by_other_user(self):
        visibles = selectors.blocs_visibles(self.co, self.user2)
        self.assertNotIn(self.bloc_perso, visibles)

    def test_personnel_bloc_visible_by_owner(self):
        visibles = selectors.blocs_visibles(self.co, self.user1)
        self.assertIn(self.bloc_perso, visibles)

    def test_is_visible_par_helper(self):
        self.assertTrue(self.bloc_societe.is_visible_par(self.user2))
        self.assertFalse(self.bloc_perso.is_visible_par(self.user2))
        self.assertTrue(self.bloc_perso.is_visible_par(self.user1))


class BlocReutilisableApiTests(TestCase):
    BLOCS = '/api/django/kb/blocs/'

    def setUp(self):
        self.co = make_company('kb-bloc-api', 'A')
        self.admin = make_user(self.co, 'kb-bloc-api-admin', role='admin')
        self.user1 = make_user(self.co, 'kb-bloc-api-u1')
        self.user2 = make_user(self.co, 'kb-bloc-api-u2')

    def test_create_bloc_forces_company_and_creator(self):
        payload = {
            'nom': 'Signature standard', 'corps': 'Cordialement,',
            'portee': 'personnel',
        }
        resp = auth(self.user1).post(self.BLOCS, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        bloc = BlocReutilisable.objects.get(id=resp.data['id'])
        self.assertEqual(bloc.company, self.co)
        self.assertEqual(bloc.created_by, self.user1)

    def test_societe_bloc_shared_personnel_private(self):
        auth(self.user1).post(
            self.BLOCS, {'nom': 'Partagé', 'corps': 'X', 'portee': 'societe'},
            format='json')
        auth(self.user1).post(
            self.BLOCS, {'nom': 'Privé', 'corps': 'Y', 'portee': 'personnel'},
            format='json')

        resp_u2 = auth(self.user2).get(self.BLOCS)
        noms_u2 = {r['nom'] for r in rows(resp_u2)}
        self.assertIn('Partagé', noms_u2)
        self.assertNotIn('Privé', noms_u2)

        resp_u1 = auth(self.user1).get(self.BLOCS)
        noms_u1 = {r['nom'] for r in rows(resp_u1)}
        self.assertIn('Partagé', noms_u1)
        self.assertIn('Privé', noms_u1)

    def test_delete_restricted_to_creator_or_admin(self):
        create_resp = auth(self.user1).post(
            self.BLOCS, {'nom': 'À moi', 'corps': 'Z', 'portee': 'personnel'},
            format='json')
        bloc_id = create_resp.data['id']

        # user2 ne peut pas le voir (donc 404, jamais 403 — pas de fuite).
        del_resp_other = auth(self.user2).delete(f'{self.BLOCS}{bloc_id}/')
        self.assertEqual(del_resp_other.status_code, 404)
        self.assertTrue(BlocReutilisable.objects.filter(id=bloc_id).exists())

        # Le créateur PEUT supprimer son propre bloc.
        del_resp_owner = auth(self.user1).delete(f'{self.BLOCS}{bloc_id}/')
        self.assertEqual(del_resp_owner.status_code, 204)
        self.assertFalse(BlocReutilisable.objects.filter(id=bloc_id).exists())

    def test_admin_can_delete_others_bloc(self):
        payload = {
            'nom': 'Partagé admin', 'corps': 'W', 'portee': 'societe',
        }
        create_resp = auth(self.user1).post(self.BLOCS, payload, format='json')
        bloc_id = create_resp.data['id']
        del_resp = auth(self.admin).delete(f'{self.BLOCS}{bloc_id}/')
        self.assertEqual(del_resp.status_code, 204)

    def test_cross_tenant_isolation(self):
        other_co = make_company('kb-bloc-api-other', 'O')
        other_user = make_user(other_co, 'kb-bloc-api-other-u1')
        BlocReutilisable.objects.create(
            company=other_co, nom='Autre société', corps='secret',
            portee=BlocReutilisable.Portee.SOCIETE, created_by=other_user)
        resp = auth(self.user1).get(self.BLOCS)
        noms = {r['nom'] for r in rows(resp)}
        self.assertNotIn('Autre société', noms)
