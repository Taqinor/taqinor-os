"""Tests ZRH10 — rapport d'évolution des compétences (« Skills Evolution »).

Couvre : monter un niveau écrit une ligne ancien->nouveau horodatée
(matrice manuelle + session de formation réalisée FG187 + quiz XRH34), le
rapport liste les progressions sur la période filtrable par employé/
compétence, isolation tenant.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    Competence,
    CompetenceEmploye,
    DossierEmploye,
    HistoriqueCompetence,
    InscriptionFormation,
    SessionFormation,
)

User = get_user_model()

URL_MATRICE = '/api/django/rh/competences-employe/'
URL_EVOLUTION = '/api/django/rh/competences/evolution/'
URL_SESSIONS = '/api/django/rh/sessions-formation/'


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


class EvolutionCompetencesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ec-a', 'A')
        self.co_b = make_company('ec-b', 'B')
        self.user_a = make_user(self.co_a, 'ec-user-a')
        self.user_b = make_user(self.co_b, 'ec-user-b')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='EC1', nom='N', prenom='P')
        self.comp = Competence.objects.create(
            company=self.co_a, code='C1', libelle='Soudure')

    def test_matrice_manuelle_ecrit_historique_creation(self):
        resp = auth(self.user_a).post(URL_MATRICE, {
            'employe': self.emp.id, 'competence': self.comp.id, 'niveau': 2,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        hist = HistoriqueCompetence.objects.get(
            employe=self.emp, competence=self.comp)
        self.assertEqual(hist.ancien_niveau, 0)
        self.assertEqual(hist.nouveau_niveau, 2)
        self.assertEqual(hist.source, HistoriqueCompetence.Source.MANUELLE)

    def test_matrice_manuelle_ecrit_historique_changement(self):
        ce = CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp, competence=self.comp,
            niveau=1)
        resp = auth(self.user_a).patch(f'{URL_MATRICE}{ce.id}/', {
            'niveau': 3,
        })
        self.assertEqual(resp.status_code, 200, resp.data)
        hist = HistoriqueCompetence.objects.get(
            employe=self.emp, competence=self.comp)
        self.assertEqual(hist.ancien_niveau, 1)
        self.assertEqual(hist.nouveau_niveau, 3)

    def test_niveau_inchange_pas_de_ligne_historique(self):
        ce = CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp, competence=self.comp,
            niveau=2)
        auth(self.user_a).patch(f'{URL_MATRICE}{ce.id}/', {'niveau': 2})
        self.assertFalse(
            HistoriqueCompetence.objects.filter(
                employe=self.emp, competence=self.comp).exists())

    def test_session_formation_realisee_ecrit_historique_formation(self):
        session = SessionFormation.objects.create(
            company=self.co_a, intitule='Sécurité',
            date_debut=date(2026, 1, 5), competence_visee=self.comp)
        InscriptionFormation.objects.create(
            company=self.co_a, session=session, participant=self.emp,
            present=True)
        resp = auth(self.user_a).post(
            f'{URL_SESSIONS}{session.id}/marquer-realisee/?niveau=3',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        hist = HistoriqueCompetence.objects.get(
            employe=self.emp, competence=self.comp)
        self.assertEqual(hist.nouveau_niveau, 3)
        self.assertEqual(hist.source, HistoriqueCompetence.Source.FORMATION)

    def test_quiz_reussi_ecrit_historique_quiz(self):
        from apps.rh.models import QuizFormation

        quiz = QuizFormation.objects.create(
            company=self.co_a, intitule='Quiz sécurité', competence=self.comp,
            questions=[{
                'question': 'Q1', 'type': 'unique', 'choix': ['a', 'b'],
                'bonnes_reponses': [0],
            }],
            score_reussite=50)
        services.passer_tentative_quiz(quiz, self.emp, reponses=[0])
        hist = HistoriqueCompetence.objects.get(
            employe=self.emp, competence=self.comp)
        self.assertEqual(hist.source, HistoriqueCompetence.Source.QUIZ)

    def test_rapport_liste_progressions_filtrable(self):
        services.enregistrer_niveau_competence(
            self.emp, self.comp.id, 2, company=self.co_a)
        services.enregistrer_niveau_competence(
            self.emp, self.comp.id, 4, company=self.co_a)
        resp = auth(self.user_a).get(
            URL_EVOLUTION, {'employe': self.emp.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 2)
        self.assertTrue(all(r['progression'] for r in resp.data))

    def test_isolation_tenant(self):
        services.enregistrer_niveau_competence(
            self.emp, self.comp.id, 2, company=self.co_a)
        resp = auth(self.user_b).get(URL_EVOLUTION)
        self.assertEqual(resp.data, [])

    def test_filtre_periode(self):
        services.enregistrer_niveau_competence(
            self.emp, self.comp.id, 1, company=self.co_a)
        demain = (timezone.localdate() + timedelta(days=1)).isoformat()
        resp = auth(self.user_a).get(
            URL_EVOLUTION, {'debut': demain})
        self.assertEqual(resp.data, [])
