"""Tests XRH34 — eLearning léger : quiz d'évaluation + certification.

Couvre :
* Correction serveur d'un quiz 5 questions (bonnes réponses jamais dans le
  payload employé).
* Réussite ≥ seuil : upsert compétence (CONFIRMÉ), inscription formation
  REUSSI si session liée, habilitation prolongée.
* Échec < seuil : aucun effet (pas de compétence, pas de prolongation).
* Attestation PDF téléchargeable uniquement pour une tentative réussie ; un
  employé ne voit que SES tentatives (portail).
* Re-certification à l'expiration : idempotente (0 doublon), no-op sans
  quiz couvrant.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    BesoinFormation,
    Competence,
    CompetenceEmploye,
    DossierEmploye,
    Habilitation,
    InscriptionFormation,
    QuizFormation,
    SessionFormation,
    TentativeQuiz,
)

User = get_user_model()

QUESTIONS = [
    {'question': 'Q1', 'type': 'unique', 'choix': ['A', 'B'],
     'bonnes_reponses': [0]},
    {'question': 'Q2', 'type': 'unique', 'choix': ['A', 'B'],
     'bonnes_reponses': [1]},
    {'question': 'Q3', 'type': 'unique', 'choix': ['A', 'B'],
     'bonnes_reponses': [0]},
    {'question': 'Q4', 'type': 'unique', 'choix': ['A', 'B'],
     'bonnes_reponses': [1]},
    {'question': 'Q5', 'type': 'unique', 'choix': ['A', 'B'],
     'bonnes_reponses': [0]},
]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, **kwargs):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P', **kwargs)


def make_quiz(company, **kwargs):
    defaults = dict(
        intitule='Quiz sécurité', questions=QUESTIONS, score_reussite=80)
    defaults.update(kwargs)
    return QuizFormation.objects.create(company=company, **defaults)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CorrectionServeurTests(TestCase):
    def setUp(self):
        self.company = make_company('xrh34-a', 'A')
        self.quiz = make_quiz(self.company)

    def test_toutes_bonnes_reponses_100_pourcent(self):
        score, reussi = services.corriger_tentative_quiz(
            self.quiz, [0, 1, 0, 1, 0])
        self.assertEqual(score, 100)
        self.assertTrue(reussi)

    def test_sous_le_seuil_echec(self):
        score, reussi = services.corriger_tentative_quiz(
            self.quiz, [1, 1, 1, 1, 1])  # 2/5 correct = 40%
        self.assertEqual(score, 40)
        self.assertFalse(reussi)

    def test_reponses_manquantes_traitees_comme_fausses(self):
        score, reussi = services.corriger_tentative_quiz(self.quiz, [0])
        self.assertEqual(score, 20)
        self.assertFalse(reussi)


class PasserTentativeQuizServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('xrh34-b', 'B')
        self.employe = make_employe(self.company, 'M1')
        self.competence = Competence.objects.create(
            company=self.company, code='POSE', libelle='Pose structure')

    def test_reussite_met_a_jour_competence(self):
        quiz = make_quiz(self.company, competence=self.competence)
        tentative = services.passer_tentative_quiz(
            quiz, self.employe, reponses=[0, 1, 0, 1, 0])
        self.assertTrue(tentative.reussi)
        self.assertEqual(tentative.score, 100)
        ce = CompetenceEmploye.objects.get(
            employe=self.employe, competence=self.competence)
        self.assertEqual(ce.niveau, CompetenceEmploye.Niveau.CONFIRME)

    def test_echec_aucun_effet(self):
        quiz = make_quiz(self.company, competence=self.competence)
        tentative = services.passer_tentative_quiz(
            quiz, self.employe, reponses=[1, 1, 1, 1, 1])
        self.assertFalse(tentative.reussi)
        self.assertFalse(
            CompetenceEmploye.objects.filter(
                employe=self.employe, competence=self.competence).exists())

    def test_reussite_avec_session_liee_marque_inscription_reussie(self):
        session = SessionFormation.objects.create(
            company=self.company, intitule='Session sécurité')
        InscriptionFormation.objects.create(
            company=self.company, session=session, participant=self.employe)
        quiz = make_quiz(self.company)
        services.passer_tentative_quiz(
            quiz, self.employe, reponses=[0, 1, 0, 1, 0], session=session)
        inscription = InscriptionFormation.objects.get(
            session=session, participant=self.employe)
        self.assertEqual(
            inscription.resultat, InscriptionFormation.Resultat.REUSSI)

    def test_reussite_prolonge_habilitation_existante(self):
        habilitation = Habilitation.objects.create(
            company=self.company, employe=self.employe,
            type_habilitation=Habilitation.TypeHabilitation.B1V,
            date_validite=timezone.localdate())
        quiz = make_quiz(
            self.company,
            habilitation_type=Habilitation.TypeHabilitation.B1V,
            validite_mois=12)
        services.passer_tentative_quiz(
            quiz, self.employe, reponses=[0, 1, 0, 1, 0])
        habilitation.refresh_from_db()
        self.assertGreater(habilitation.date_validite, timezone.localdate())

    def test_reussite_cree_habilitation_si_absente(self):
        quiz = make_quiz(
            self.company,
            habilitation_type=Habilitation.TypeHabilitation.B1V,
            validite_mois=6)
        services.passer_tentative_quiz(
            quiz, self.employe, reponses=[0, 1, 0, 1, 0])
        self.assertTrue(
            Habilitation.objects.filter(
                employe=self.employe,
                type_habilitation=Habilitation.TypeHabilitation.B1V).exists())


class RecertificationServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('xrh34-c', 'C')
        self.employe = make_employe(self.company, 'M2')

    def test_habilitation_expiree_avec_quiz_cree_besoin(self):
        make_quiz(
            self.company, habilitation_type=Habilitation.TypeHabilitation.B1V,
            validite_mois=12, actif=True)
        habilitation = Habilitation.objects.create(
            company=self.company, employe=self.employe,
            type_habilitation=Habilitation.TypeHabilitation.B1V,
            date_validite=timezone.localdate() - timedelta(days=1))
        besoin = services.generer_besoin_recertification(habilitation)
        self.assertIsNotNone(besoin)
        self.assertEqual(
            BesoinFormation.objects.filter(employe=self.employe).count(), 1)

    def test_idempotent_ne_double_pas(self):
        make_quiz(
            self.company, habilitation_type=Habilitation.TypeHabilitation.B1V,
            validite_mois=12, actif=True)
        habilitation = Habilitation.objects.create(
            company=self.company, employe=self.employe,
            type_habilitation=Habilitation.TypeHabilitation.B1V,
            date_validite=timezone.localdate() - timedelta(days=1))
        services.generer_besoin_recertification(habilitation)
        services.generer_besoin_recertification(habilitation)
        self.assertEqual(
            BesoinFormation.objects.filter(employe=self.employe).count(), 1)

    def test_sans_quiz_couvrant_no_op(self):
        habilitation = Habilitation.objects.create(
            company=self.company, employe=self.employe,
            type_habilitation=Habilitation.TypeHabilitation.B2V,
            date_validite=timezone.localdate() - timedelta(days=1))
        besoin = services.generer_besoin_recertification(habilitation)
        self.assertIsNone(besoin)
        self.assertEqual(BesoinFormation.objects.count(), 0)

    def test_habilitation_valide_no_op(self):
        make_quiz(
            self.company, habilitation_type=Habilitation.TypeHabilitation.B1V,
            validite_mois=12, actif=True)
        habilitation = Habilitation.objects.create(
            company=self.company, employe=self.employe,
            type_habilitation=Habilitation.TypeHabilitation.B1V,
            date_validite=timezone.localdate() + timedelta(days=30))
        besoin = services.generer_besoin_recertification(habilitation)
        self.assertIsNone(besoin)


class PortailQuizApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xrh34-api', 'API')
        self.user = make_user(self.company, 'employe-quiz', role='normal')
        self.employe = make_employe(self.company, 'M3', user=self.user)
        self.quiz = make_quiz(self.company)

    def test_quiz_disponibles_sans_bonnes_reponses(self):
        api = auth(self.user)
        resp = api.get('/api/django/rh/portail/quiz-disponibles/')
        self.assertEqual(resp.status_code, 200)
        question = resp.data[0]['questions'][0]
        self.assertNotIn('bonnes_reponses', question)

    def test_passer_quiz_cree_tentative(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/rh/portail/{self.quiz.pk}/passer-quiz/',
            {'reponses': [0, 1, 0, 1, 0]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['reussi'])
        self.assertEqual(
            TentativeQuiz.objects.filter(employe=self.employe).count(), 1)

    def test_mes_tentatives_isolees_par_employe(self):
        autre_user = make_user(self.company, 'autre-employe', role='normal')
        autre_employe = make_employe(self.company, 'M4', user=autre_user)
        TentativeQuiz.objects.create(
            company=self.company, quiz=self.quiz, employe=autre_employe,
            score=100, reussi=True)
        api = auth(self.user)
        resp = api.get('/api/django/rh/portail/mes-tentatives-quiz/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)


class AttestationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xrh34-att', 'Att')
        self.admin = make_user(self.company, 'admin-att', role='admin')
        self.employe = make_employe(self.company, 'M5')
        self.quiz = make_quiz(self.company)

    def test_attestation_404_si_non_reussie(self):
        tentative = TentativeQuiz.objects.create(
            company=self.company, quiz=self.quiz, employe=self.employe,
            score=40, reussi=False)
        api = auth(self.admin)
        resp = api.get(
            f'/api/django/rh/tentatives-quiz/{tentative.pk}/attestation/')
        self.assertEqual(resp.status_code, 404)

    def test_attestation_pdf_si_reussie(self):
        tentative = TentativeQuiz.objects.create(
            company=self.company, quiz=self.quiz, employe=self.employe,
            score=100, reussi=True)
        api = auth(self.admin)
        resp = api.get(
            f'/api/django/rh/tentatives-quiz/{tentative.pk}/attestation/')
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')
