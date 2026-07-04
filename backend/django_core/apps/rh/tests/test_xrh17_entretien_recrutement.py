"""Tests XRH17 — Entretiens de recrutement (planification + grille
d'évaluation).

Couvre :
* planifier un entretien, noter à 2 évaluateurs ;
* le comparatif classe les candidats de la même ouverture par moyenne
  décroissante ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Candidature, EntretienRecrutement, OuverturePoste

User = get_user_model()

ENTRETIENS = '/api/django/rh/entretiens-recrutement/'
CANDIDATURES = '/api/django/rh/candidatures/'


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


class EntretienRecrutementTests(TestCase):
    def setUp(self):
        self.co = make_company('entr-a', 'A')
        self.rh1 = make_user(self.co, 'entr-rh1')
        self.rh2 = make_user(self.co, 'entr-rh2')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose')
        self.cand_bon = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Karim Idrissi')
        self.cand_moyen = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Sara Bouzid')

    def test_planifier_et_noter_deux_evaluateurs(self):
        resp = auth(self.rh1).post(ENTRETIENS, {
            'candidature': self.cand_bon.id,
            'date_heure': '2026-07-10T10:00:00Z',
            'type': EntretienRecrutement.TypeEntretien.TECHNIQUE,
            'evaluateurs': [self.rh1.id, self.rh2.id],
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        entretien_id = resp.data['id']

        resp1 = auth(self.rh1).post(
            f'{ENTRETIENS}{entretien_id}/noter/', {
                'notes_criteres': {'technique': 4, 'communication': 5},
                'avis': 'favorable',
            }, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)

        resp2 = auth(self.rh2).post(
            f'{ENTRETIENS}{entretien_id}/noter/', {
                'notes_criteres': {'technique': 3, 'communication': 3},
                'avis': 'reserve',
            }, format='json')
        self.assertEqual(resp2.status_code, 201, resp2.data)

        detail = auth(self.rh1).get(f'{ENTRETIENS}{entretien_id}/')
        self.assertEqual(len(detail.data['notes']), 2)

    def test_noter_deux_fois_meme_evaluateur_met_a_jour(self):
        resp = auth(self.rh1).post(ENTRETIENS, {
            'candidature': self.cand_bon.id,
            'type': EntretienRecrutement.TypeEntretien.RH,
        })
        entretien_id = resp.data['id']
        auth(self.rh1).post(
            f'{ENTRETIENS}{entretien_id}/noter/',
            {'notes_criteres': {'a': 2}, 'avis': 'reserve'}, format='json')
        auth(self.rh1).post(
            f'{ENTRETIENS}{entretien_id}/noter/',
            {'notes_criteres': {'a': 5}, 'avis': 'favorable'}, format='json')
        detail = auth(self.rh1).get(f'{ENTRETIENS}{entretien_id}/')
        self.assertEqual(len(detail.data['notes']), 1)
        self.assertEqual(detail.data['notes'][0]['avis'], 'favorable')

    def test_comparatif_classe_par_moyenne_decroissante(self):
        e1 = EntretienRecrutement.objects.create(
            company=self.co, candidature=self.cand_bon)
        e2 = EntretienRecrutement.objects.create(
            company=self.co, candidature=self.cand_moyen)
        auth(self.rh1).post(
            f'{ENTRETIENS}{e1.id}/noter/',
            {'notes_criteres': {'a': 5, 'b': 5}, 'avis': 'favorable'},
            format='json')
        auth(self.rh1).post(
            f'{ENTRETIENS}{e2.id}/noter/',
            {'notes_criteres': {'a': 2, 'b': 2}, 'avis': 'defavorable'},
            format='json')

        resp = auth(self.rh1).get(
            f'{CANDIDATURES}{self.cand_bon.id}/comparatif/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['candidature_id'], self.cand_bon.id)
        self.assertEqual(resp.data[0]['moyenne'], 5.0)
        self.assertEqual(resp.data[1]['candidature_id'], self.cand_moyen.id)

    def test_isolation_societe(self):
        co_b = make_company('entr-b', 'B')
        rh_b = make_user(co_b, 'entr-rh-b')
        entretien = EntretienRecrutement.objects.create(
            company=self.co, candidature=self.cand_bon)
        resp = auth(rh_b).get(f'{ENTRETIENS}{entretien.id}/')
        self.assertEqual(resp.status_code, 404)
