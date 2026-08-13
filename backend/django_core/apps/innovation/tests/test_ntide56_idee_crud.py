"""Tests CRUD consolidés de la boîte à idées (NTIDE56).

Un module unique qui couvre, bout-en-bout via l'API, les 8 critères
d'acceptation de NTIDE56 : création (``company`` posée par le SERVEUR,
jamais lue du corps), liste (filtrée société), détail, vote (unique),
mise à jour du compteur dénormalisé ``votes_count``, drapeau brouillon
(NTIDE18), masquage de modération (NTIDE19) et permissions
« lecteur » (utilisateur simple) vs « Directeur » (palier admin).

Les tests par fonctionnalité existent déjà par ailleurs
(``test_vote.py``/``test_draft.py``/``test_moderation.py``…) : ce module est
la vérification de non-régression du PARCOURS CRUD complet demandé par
NTIDE56, volontairement autoportant (aucun import croisé de fixtures).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import Idee, VoteIdee

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


class IdeeCrudTests(TestCase):
    BASE = '/api/django/innovation/idees/'
    VOTES = '/api/django/innovation/votes/'

    def setUp(self):
        self.co_a = make_company('innov-ntide56-a', 'A')
        self.co_b = make_company('innov-ntide56-b', 'B')
        self.auteur = make_user(self.co_a, 'ntide56-auteur')
        self.collegue = make_user(self.co_a, 'ntide56-collegue')
        self.directeur = make_user(self.co_a, 'ntide56-directeur', role='admin')
        self.user_b = make_user(self.co_b, 'ntide56-user-b')

    # ── 1. création : company posée par le serveur ──────────────────────────
    def test_create_company_is_server_set(self):
        resp = auth(self.auteur).post(self.BASE, {
            'titre': 'Idée NTIDE56',
            'description': 'Proposée par le test CRUD.',
            # Tentative d'injection : le corps NE DOIT PAS pouvoir choisir la
            # société ni l'auteur (multi-tenant, CLAUDE.md).
            'company': self.co_b.id,
            'auteur': self.user_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        idee = Idee.objects.get(id=resp.data['id'])
        self.assertEqual(idee.company, self.co_a)
        self.assertEqual(idee.auteur, self.auteur)

    # ── 2. liste : filtrée par société ──────────────────────────────────────
    def test_list_filtered_by_company(self):
        mienne = Idee.objects.create(
            company=self.co_a, titre='Chez A', auteur=self.auteur)
        Idee.objects.create(company=self.co_b, titre='Chez B',
                            auteur=self.user_b)
        resp = auth(self.collegue).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [mienne.id])

    # ── 3. détail ───────────────────────────────────────────────────────────
    def test_detail_ok_and_cross_tenant_404(self):
        mienne = Idee.objects.create(
            company=self.co_a, titre='Détail A', auteur=self.auteur)
        autre = Idee.objects.create(
            company=self.co_b, titre='Détail B', auteur=self.user_b)
        api = auth(self.collegue)
        ok = api.get(f'{self.BASE}{mienne.id}/')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data['titre'], 'Détail A')
        self.assertEqual(api.get(f'{self.BASE}{autre.id}/').status_code, 404)

    # ── 4. vote unique ──────────────────────────────────────────────────────
    def test_vote_is_unique_per_voter(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='À voter', auteur=self.auteur)
        api = auth(self.collegue)
        premier = api.post(self.VOTES, {'idee': idee.id}, format='json')
        self.assertEqual(premier.status_code, 201, premier.data)
        second = api.post(self.VOTES, {'idee': idee.id}, format='json')
        self.assertEqual(second.status_code, 400)
        self.assertEqual(
            VoteIdee.objects.filter(idee=idee, votant=self.collegue).count(), 1)

    # ── 5. compteur dénormalisé mis à jour ──────────────────────────────────
    def test_votes_count_updated_on_vote_and_unvote(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Compteur', auteur=self.auteur)
        api = auth(self.collegue)
        cree = api.post(self.VOTES, {'idee': idee.id}, format='json')
        idee.refresh_from_db()
        self.assertEqual(idee.votes_count, 1)
        api.delete(f'{self.VOTES}{cree.data["id"]}/')
        idee.refresh_from_db()
        self.assertEqual(idee.votes_count, 0)

    # ── 6. drapeau brouillon (NTIDE18) ──────────────────────────────────────
    def test_draft_visible_only_to_author(self):
        resp = auth(self.auteur).post(self.BASE, {
            'titre': 'Brouillon NTIDE56', 'draft': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        idee_id = resp.data['id']
        self.assertTrue(Idee.objects.get(id=idee_id).draft)
        vus_auteur = [r['id'] for r in rows(auth(self.auteur).get(self.BASE))]
        self.assertIn(idee_id, vus_auteur)
        vus_collegue = [r['id'] for r in rows(auth(self.collegue).get(self.BASE))]
        self.assertNotIn(idee_id, vus_collegue)

    # ── 7. masquage de modération (NTIDE19) ─────────────────────────────────
    def test_moderation_masquage_hides_from_list(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='À masquer', auteur=self.auteur)
        masquer = auth(self.directeur).post(f'{self.BASE}{idee.id}/masquer/')
        self.assertEqual(masquer.status_code, 200, masquer.data)
        idee.refresh_from_db()
        self.assertTrue(idee.archived)
        vus = [r['id'] for r in rows(auth(self.collegue).get(self.BASE))]
        self.assertNotIn(idee.id, vus)
        # Jamais supprimée — le palier admin la retrouve explicitement.
        retrouvee = auth(self.directeur).get(self.BASE, {'include_archived': '1'})
        self.assertIn(idee.id, [r['id'] for r in rows(retrouvee)])

    # ── 8. permissions : utilisateur simple vs Directeur ────────────────────
    def test_status_transition_reserved_to_directeur(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Transition', auteur=self.auteur)
        refuse = auth(self.collegue).post(f'{self.BASE}{idee.id}/examiner/')
        self.assertEqual(refuse.status_code, 403)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.OUVERT)
        ok = auth(self.directeur).post(f'{self.BASE}{idee.id}/examiner/')
        self.assertEqual(ok.status_code, 200, ok.data)
        idee.refresh_from_db()
        self.assertEqual(idee.statut, Idee.Statut.EXAMINEE)

    def test_moderation_refused_to_simple_user(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Modération refusée', auteur=self.auteur)
        resp = auth(self.collegue).post(f'{self.BASE}{idee.id}/masquer/')
        self.assertEqual(resp.status_code, 403)
        idee.refresh_from_db()
        self.assertFalse(idee.archived)

    def test_anonymous_refused_everywhere(self):
        idee = Idee.objects.create(
            company=self.co_a, titre='Anonyme', auteur=self.auteur)
        api = APIClient()
        self.assertEqual(api.get(self.BASE).status_code, 401)
        self.assertEqual(api.get(f'{self.BASE}{idee.id}/').status_code, 401)
        self.assertEqual(
            api.post(self.BASE, {'titre': 'x'}, format='json').status_code, 401)

    def test_idee_is_never_deleted(self):
        """Aucun ``destroy`` : une idée se ferme, elle ne se supprime pas."""
        idee = Idee.objects.create(
            company=self.co_a, titre='Jamais supprimée', auteur=self.auteur)
        resp = auth(self.directeur).delete(f'{self.BASE}{idee.id}/')
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Idee.objects.filter(id=idee.id).exists())
