"""Tests PROJ15 — Profil ressource & équipes (RH-léger, cout_horaire interne).

Couvre : société posée côté serveur, isolation entre sociétés, membership
d'équipe, filtres ``?actif`` et ``?membre``, validation des membres
d'une autre société → 400.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Equipe, RessourceProfil

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


BASE_RESSOURCES = '/api/django/gestion-projet/ressources/'
BASE_EQUIPES = '/api/django/gestion-projet/equipes/'


class RessourceProfilApiTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj15-rp-a', 'A')
        self.co_b = make_company('proj15-rp-b', 'B')
        self.user_a = make_user(self.co_a, 'proj15-rp-ua')
        self.user_b = make_user(self.co_b, 'proj15-rp-ub')

    def _payload(self, **kw):
        return {'nom': 'Youssef Technicien', 'role': 'Technicien pose', **kw}

    # ── création ─────────────────────────────────────────────────────────────

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(BASE_RESSOURCES, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = RessourceProfil.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_cout_horaire_stored_and_returned(self):
        api = auth(self.user_a)
        resp = api.post(
            BASE_RESSOURCES,
            self._payload(cout_horaire='120.50'),
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['cout_horaire']), Decimal('120.50'))
        obj = RessourceProfil.objects.get(id=resp.data['id'])
        self.assertEqual(obj.cout_horaire, Decimal('120.50'))

    def test_actif_defaults_to_true(self):
        api = auth(self.user_a)
        resp = api.post(BASE_RESSOURCES, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['actif'])

    # ── isolation entre sociétés ──────────────────────────────────────────────

    def test_list_isolation(self):
        RessourceProfil.objects.create(
            company=self.co_a, nom='Ressource A', cout_horaire=Decimal('0'))
        resp = auth(self.user_b).get(BASE_RESSOURCES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_detail_isolation(self):
        r = RessourceProfil.objects.create(
            company=self.co_a, nom='Ressource A2', cout_horaire=Decimal('0'))
        resp = auth(self.user_b).get(f'{BASE_RESSOURCES}{r.id}/')
        self.assertEqual(resp.status_code, 404)

    # ── filtre ?actif ─────────────────────────────────────────────────────────

    def test_filter_actif(self):
        RessourceProfil.objects.create(
            company=self.co_a, nom='Actif', actif=True, cout_horaire=Decimal('0'))
        RessourceProfil.objects.create(
            company=self.co_a, nom='Inactif', actif=False, cout_horaire=Decimal('0'))
        api = auth(self.user_a)
        resp = api.get(BASE_RESSOURCES + '?actif=1')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Actif', noms)
        self.assertNotIn('Inactif', noms)

    # ── accès role normal ─────────────────────────────────────────────────────

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'proj15-rp-normal', role='normal')
        resp = auth(normal).get(BASE_RESSOURCES)
        self.assertEqual(resp.status_code, 403)


class EquipeApiTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj15-eq-a', 'A')
        self.co_b = make_company('proj15-eq-b', 'B')
        self.user_a = make_user(self.co_a, 'proj15-eq-ua')
        self.user_b = make_user(self.co_b, 'proj15-eq-ub')
        self.r1 = RessourceProfil.objects.create(
            company=self.co_a, nom='Hamza Poseur', cout_horaire=Decimal('90'))
        self.r2 = RessourceProfil.objects.create(
            company=self.co_a, nom='Aicha Electricienne', cout_horaire=Decimal('80'))
        self.r_b = RessourceProfil.objects.create(
            company=self.co_b, nom='Ressource B', cout_horaire=Decimal('0'))

    # ── création et membership ────────────────────────────────────────────────

    def test_create_equipe_forces_company(self):
        api = auth(self.user_a)
        payload = {'nom': 'Equipe Casa Nord', 'membres': [self.r1.id, self.r2.id]}
        resp = api.post(BASE_EQUIPES, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Equipe.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertCountEqual(
            list(obj.membres.values_list('id', flat=True)),
            [self.r1.id, self.r2.id],
        )

    def test_membres_detail_embedded(self):
        api = auth(self.user_a)
        payload = {'nom': 'Equipe Detail', 'membres': [self.r1.id]}
        resp = api.post(BASE_EQUIPES, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        noms = [m['nom'] for m in resp.data['membres_detail']]
        self.assertIn('Hamza Poseur', noms)

    # ── validation membre autre société → 400 ─────────────────────────────────

    def test_membre_autre_societe_refuse(self):
        api = auth(self.user_a)
        payload = {'nom': 'Equipe Invalide', 'membres': [self.r_b.id]}
        resp = api.post(BASE_EQUIPES, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── isolation ─────────────────────────────────────────────────────────────

    def test_list_isolation(self):
        Equipe.objects.create(company=self.co_a, nom='Equipe A Seule')
        resp = auth(self.user_b).get(BASE_EQUIPES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    # ── filtre ?membre ────────────────────────────────────────────────────────

    def test_filter_par_membre(self):
        eq1 = Equipe.objects.create(company=self.co_a, nom='Equipe Filtre 1')
        eq1.membres.set([self.r1])
        eq2 = Equipe.objects.create(company=self.co_a, nom='Equipe Filtre 2')
        eq2.membres.set([self.r2])
        api = auth(self.user_a)
        resp = api.get(f'{BASE_EQUIPES}?membre={self.r1.id}')
        noms = [e['nom'] for e in rows(resp)]
        self.assertIn('Equipe Filtre 1', noms)
        self.assertNotIn('Equipe Filtre 2', noms)
