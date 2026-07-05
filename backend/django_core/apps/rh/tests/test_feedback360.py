"""Tests ZRH9 — feedback 360° (avis multi-sources sur un entretien).

Couvre : invitation de N répondants, chaque répondant ne voit/remplit que
son propre retour (403/404 pour un autre), synthèse agrège et masque sous
le seuil d'anonymat, isolation tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    CampagneEvaluation,
    DossierEmploye,
    EvaluationEmploye,
    RetourFeedback360,
)

User = get_user_model()

PORTAIL = '/api/django/rh/portail/'
RETOURS = '/api/django/rh/retours-feedback360/'


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


class Feedback360Tests(TestCase):
    def setUp(self):
        self.co_a = make_company('fb-a', 'A')
        self.co_b = make_company('fb-b', 'B')
        self.responsable = make_user(self.co_a, 'fb-resp')
        self.campagne = CampagneEvaluation.objects.create(
            company=self.co_a, intitule='Annuel 2026', annee=2026)
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='FB0', nom='Evalue', prenom='X')
        self.evaluation = EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.campagne, employe=self.emp)
        self.rep_users = []
        self.rep_dossiers = []
        for i in range(3):
            u = make_user(self.co_a, f'fb-rep-{i}', role='normal')
            d = DossierEmploye.objects.create(
                company=self.co_a, matricule=f'FBR{i}', nom='Rep',
                prenom=str(i), user=u)
            self.rep_users.append(u)
            self.rep_dossiers.append(d)

    def _invite(self, dossier, relation='pair'):
        return RetourFeedback360.objects.create(
            company=self.co_a, evaluation=self.evaluation,
            repondant=dossier, relation=relation)

    def test_inviter_3_repondants(self):
        for d in self.rep_dossiers:
            resp = auth(self.responsable).post(RETOURS, {
                'evaluation': self.evaluation.id, 'repondant': d.id,
                'relation': 'pair',
            })
            self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            RetourFeedback360.objects.filter(
                evaluation=self.evaluation).count(), 3)

    def test_repondant_soumet_son_propre_retour(self):
        retour = self._invite(self.rep_dossiers[0])
        resp = auth(self.rep_users[0]).patch(
            f'{PORTAIL}{retour.id}/mon-feedback360/', {
                'reponses': {'communication': 4}, 'commentaire': 'Bien',
                'soumis': True,
            })
        self.assertEqual(resp.status_code, 200, resp.data)
        retour.refresh_from_db()
        self.assertTrue(retour.soumis)
        self.assertIsNotNone(retour.date_soumission)

    def test_repondant_ne_voit_pas_retour_dautrui(self):
        retour_autre = self._invite(self.rep_dossiers[1])
        resp = auth(self.rep_users[0]).patch(
            f'{PORTAIL}{retour_autre.id}/mon-feedback360/', {
                'reponses': {'communication': 5},
            })
        self.assertEqual(resp.status_code, 404)

    def test_synthese_masque_sous_seuil(self):
        retour1 = self._invite(self.rep_dossiers[0])
        retour1.reponses = {'communication': 4}
        retour1.soumis = True
        retour1.save()
        retour2 = self._invite(self.rep_dossiers[1])
        retour2.reponses = {'communication': 2}
        retour2.soumis = True
        retour2.save()
        resp = auth(self.responsable).get(
            f'{RETOURS}synthese/', {'evaluation': self.evaluation.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['anonymise'])
        self.assertNotIn('retours', resp.data)
        self.assertEqual(resp.data['nb_soumis'], 2)
        self.assertEqual(
            resp.data['moyennes_par_critere']['communication'], 3.0)

    def test_synthese_expose_retours_au_seuil(self):
        for i, note in enumerate([4, 2, 5]):
            retour = self._invite(self.rep_dossiers[i])
            retour.reponses = {'communication': note}
            retour.soumis = True
            retour.save()
        resp = auth(self.responsable).get(
            f'{RETOURS}synthese/', {'evaluation': self.evaluation.id})
        self.assertFalse(resp.data['anonymise'])
        self.assertEqual(len(resp.data['retours']), 3)

    def test_isolation_tenant(self):
        user_b = make_user(self.co_b, 'fb-user-b')
        resp = auth(user_b).get(RETOURS)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows), 0)
