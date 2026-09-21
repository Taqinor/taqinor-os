"""Tests API de la boîte à idées (NTIDE1 modèle, NTIDE4 liste + filtres).

Couvre : société + auteur posés côté serveur (jamais du corps), isolation
multi-société, accès ouvert à TOUT utilisateur connecté (« logged-in users
only », NTIDE4), filtres statut/contexte/owner/created_since, tri par votes,
``statut`` non modifiable par PATCH direct, aucun DELETE exposé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class IdeeApiTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-a', 'A')
        self.co_b = make_company('innov-b', 'B')
        # role_legacy='normal' — le plus limité : NTIDE4 exige que même ce
        # palier puisse lister/proposer des idées (« logged-in users only »).
        self.user_a = make_user(self.co_a, 'innov-a')
        self.user_b = make_user(self.co_b, 'innov-b')

    def _payload(self, **kw):
        base = {'titre': 'Ajouter un export PDF', 'contexte': 'SAV'}
        base.update(kw)
        return base

    # ── Création : société + auteur côté serveur ────────────────────────────
    def test_create_forces_company_and_auteur_server_side(self):
        resp = auth(self.user_a).post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Idee.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.auteur, self.user_a)
        self.assertEqual(obj.statut, Idee.Statut.OUVERT)
        self.assertEqual(obj.votes_count, 0)

    def test_create_ignores_company_in_body(self):
        payload = self._payload()
        payload['company'] = self.co_b.id
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Idee.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_any_authenticated_role_can_propose(self):
        """NTIDE4 — « logged-in users only » : même le rôle le plus limité
        (normal) peut proposer une idée."""
        resp = auth(self.user_a).post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_anonymous_refused(self):
        resp = APIClient().get(self.BASE)
        self.assertEqual(resp.status_code, 401)

    # ── Isolation multi-société ──────────────────────────────────────────────
    def test_list_isolation(self):
        Idee.objects.create(company=self.co_a, titre='A only')
        resp_b = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp_b.status_code, 200)
        self.assertEqual(len(rows(resp_b)), 0)

    # ── Filtres (NTIDE4) ──────────────────────────────────────────────────────
    def test_filter_by_statut(self):
        Idee.objects.create(
            company=self.co_a, titre='Ouverte', statut=Idee.Statut.OUVERT)
        Idee.objects.create(
            company=self.co_a, titre='Retenue', statut=Idee.Statut.RETENUE)
        resp = auth(self.user_a).get(self.BASE, {'statut': 'retenue'})
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'Retenue')

    def test_filter_by_contexte(self):
        Idee.objects.create(company=self.co_a, titre='Devis', contexte='Devis')
        Idee.objects.create(company=self.co_a, titre='Stock', contexte='Stock')
        resp = auth(self.user_a).get(self.BASE, {'contexte': 'Stock'})
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'Stock')

    def test_filter_by_owner(self):
        other = make_user(self.co_a, 'innov-a-other')
        Idee.objects.create(company=self.co_a, titre='De A', auteur=self.user_a)
        Idee.objects.create(company=self.co_a, titre='De other', auteur=other)
        resp = auth(self.user_a).get(self.BASE, {'owner': other.id})
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'De other')

    def test_filter_created_since_excludes_older(self):
        from django.utils import timezone
        Idee.objects.create(company=self.co_a, titre='Ancienne')
        futur = (timezone.now() + timezone.timedelta(days=1)).isoformat()
        resp = auth(self.user_a).get(self.BASE, {'created_since': futur})
        self.assertEqual(len(rows(resp)), 0)

    def test_ordering_by_votes_count(self):
        low = Idee.objects.create(
            company=self.co_a, titre='Peu de votes', votes_count=1)
        high = Idee.objects.create(
            company=self.co_a, titre='Populaire', votes_count=9)
        resp = auth(self.user_a).get(self.BASE, {'ordering': '-votes_count'})
        data = rows(resp)
        self.assertEqual(data[0]['id'], high.id)
        self.assertEqual(data[1]['id'], low.id)

    # ── Statut : non modifiable par PATCH direct ────────────────────────────
    def test_statut_not_writable_via_patch(self):
        idee = Idee.objects.create(company=self.co_a, titre='X')
        resp = auth(self.user_a).patch(
            f'{self.BASE}{idee.id}/', {'statut': Idee.Statut.RETENUE},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.OUVERT)

    def test_votes_count_not_writable_via_patch(self):
        idee = Idee.objects.create(company=self.co_a, titre='X')
        auth(self.user_a).patch(
            f'{self.BASE}{idee.id}/', {'votes_count': 99}, format='json')
        idee.refresh_from_db()
        self.assertEqual(idee.votes_count, 0)

    # ── Pas de suppression exposée ───────────────────────────────────────────
    def test_destroy_not_allowed(self):
        idee = Idee.objects.create(company=self.co_a, titre='X')
        resp = auth(self.user_a).delete(f'{self.BASE}{idee.id}/')
        self.assertEqual(resp.status_code, 405)
