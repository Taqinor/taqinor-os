"""Tests XRH32 — Baromètre interne eNPS anonyme (pulse).

Couvre :
* double vote impossible (409, une seule ``ParticipationPulse`` par
  (campagne, user)) ;
* la réponse est STRUCTURELLEMENT non reliable au votant (test de schéma :
  ``ReponsePulse`` ne porte AUCUNE FK user/employe) ;
* le score eNPS (%promoteurs − %détracteurs) est correct ;
* les résultats sont masqués sous 5 réponses (anonymat) ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors, services
from apps.rh.models import CampagnePulse, ParticipationPulse, ReponsePulse

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


class SchemaAnonymatTests(TestCase):
    def test_reponse_pulse_aucune_fk_user_ou_employe(self):
        """Garde-fou structurel : le modèle ne peut PAS relier une réponse
        au votant — aucun champ ``user``/``employe`` sur ``ReponsePulse``."""
        noms_champs = {f.name for f in ReponsePulse._meta.get_fields()}
        self.assertNotIn('user', noms_champs)
        self.assertNotIn('employe', noms_champs)


class RepondrePulseTests(TestCase):
    def setUp(self):
        self.co = make_company('pulse-a', 'A')
        self.rh = make_user(self.co, 'pulse-rh')
        self.employe1 = make_user(self.co, 'pulse-e1', role='normal')
        self.employe2 = make_user(self.co, 'pulse-e2', role='normal')
        self.campagne = CampagnePulse.objects.create(company=self.co)

    def test_double_vote_impossible_service(self):
        services.repondre_pulse(self.campagne, self.employe1, score=8)
        with self.assertRaises(services.DejaVoteError):
            services.repondre_pulse(self.campagne, self.employe1, score=5)
        self.assertEqual(
            ParticipationPulse.objects.filter(
                campagne=self.campagne, user=self.employe1).count(), 1)
        self.assertEqual(
            ReponsePulse.objects.filter(campagne=self.campagne).count(), 1)

    def test_double_vote_api_409(self):
        api = auth(self.employe1)
        url = f'/api/django/rh/campagnes-pulse/{self.campagne.id}/repondre/'
        resp1 = api.post(url, {'score': 9}, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)
        resp2 = api.post(url, {'score': 3}, format='json')
        self.assertEqual(resp2.status_code, 409, resp2.data)

    def test_vote_score_hors_bornes_rejete(self):
        api = auth(self.employe1)
        url = f'/api/django/rh/campagnes-pulse/{self.campagne.id}/repondre/'
        resp = api.post(url, {'score': 15}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_reponse_ne_reference_pas_le_votant(self):
        services.repondre_pulse(self.campagne, self.employe1, score=7)
        reponse = ReponsePulse.objects.get(campagne=self.campagne)
        # Aucun moyen de retrouver le votant depuis la réponse.
        self.assertFalse(hasattr(reponse, 'user'))
        self.assertFalse(hasattr(reponse, 'employe'))


class ScoreEnpsTests(TestCase):
    def setUp(self):
        self.co = make_company('pulse-b', 'A')
        self.rh = make_user(self.co, 'pulse-rh-b')
        self.campagne = CampagnePulse.objects.create(company=self.co)

    def _voter(self, n, score):
        for i in range(n):
            user = make_user(self.co, f'pulse-voter-{score}-{i}', role='normal')
            services.repondre_pulse(self.campagne, user, score=score)

    def test_masque_sous_cinq_reponses(self):
        self._voter(4, 9)
        result = selectors.score_enps_campagne(self.co, self.campagne.id)
        self.assertTrue(result['masque'])
        self.assertIsNone(result['score_enps'])
        self.assertEqual(result['nb_reponses'], 4)

    def test_score_correct_au_dela_du_seuil(self):
        # 4 promoteurs (9-10), 1 passif (7-8), 1 détracteur (0-6) = 6 réponses.
        self._voter(4, 10)
        self._voter(1, 7)
        self._voter(1, 3)
        result = selectors.score_enps_campagne(self.co, self.campagne.id)
        self.assertFalse(result['masque'])
        self.assertEqual(result['nb_reponses'], 6)
        # (4 - 1) / 6 * 100 = 50.0
        self.assertEqual(result['score_enps'], 50.0)

    def test_resultats_endpoint_gate_admin(self):
        self._voter(5, 9)
        resp = auth(self.rh).get(
            f'/api/django/rh/campagnes-pulse/{self.campagne.id}/resultats/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['masque'])

    def test_resultats_endpoint_ferme_role_normal(self):
        normal = make_user(self.co, 'pulse-normal-viewer', role='normal')
        resp = auth(normal).get(
            f'/api/django/rh/campagnes-pulse/{self.campagne.id}/resultats/')
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe(self):
        co_b = make_company('pulse-c', 'B')
        rh_b = make_user(co_b, 'pulse-rh-c')
        self._voter(5, 9)
        campagne_b = CampagnePulse.objects.create(company=co_b)
        resp = auth(rh_b).get(
            f'/api/django/rh/campagnes-pulse/{campagne_b.id}/resultats/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_reponses'], 0)
