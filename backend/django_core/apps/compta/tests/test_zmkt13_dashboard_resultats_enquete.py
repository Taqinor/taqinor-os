"""ZMKT13 — Tableau de bord résultats d'enquête + liste des participations.

Couvre : la page résultats montre les agrégats par question + le taux de
complétion, la liste des participations affiche chaque soumission avec
score et durée, company-scoped, export XLSX, tests des agrégats.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Enquete
from apps.crm.models import Lead


QUESTIONS_SCOREES = [
    {'id': 'q1', 'type': 'choix', 'libelle': 'Q1', 'options': ['a', 'b'],
     'points': 10, 'bonne_reponse': 'a'},
]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DashboardResultatsEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt13', 'ZMKT13')

    def test_participations_liste_avec_score(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz', questions=QUESTIONS_SCOREES)
        enquete.mode_scoring = Enquete.ModeScoring.AVEC_REPONSES
        enquete.score_requis_pct = 50
        enquete.save(update_fields=['mode_scoring', 'score_requis_pct'])
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'a'})
        participations = services.participations_enquete(enquete)
        self.assertEqual(len(participations), 1)
        self.assertEqual(float(participations[0]['score_pct']), 100.0)
        self.assertTrue(participations[0]['reussi'])

    def test_participations_filtre_reussi(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz2', questions=QUESTIONS_SCOREES)
        enquete.mode_scoring = Enquete.ModeScoring.AVEC_REPONSES
        enquete.score_requis_pct = 50
        enquete.save(update_fields=['mode_scoring', 'score_requis_pct'])
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'a'})
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'b'})
        reussis = services.participations_enquete(enquete, reussi=True)
        echecs = services.participations_enquete(enquete, reussi=False)
        self.assertEqual(len(reussis), 1)
        self.assertEqual(len(echecs), 1)

    def test_participation_avec_lead_identifie(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz3', questions=[{'id': 'q1', 'type': 'texte'}])
        lead = Lead.objects.create(company=self.co, nom='Client', prenom='X')
        services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'ok'}, contact_ref=f'lead:{lead.id}')
        participations = services.participations_enquete(enquete)
        self.assertIn('Client', participations[0]['contact'])

    def test_resultats_endpoint_agrege(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz4', questions=[
                {'id': 'q1', 'type': 'choix', 'options': ['a', 'b']}])
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'a'})
        analytics = services.analytics_enquete(enquete)
        self.assertIn('_completion', analytics)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt13-b', 'ZMKT13-B')
        enquete = services.creer_enquete(
            self.co, titre='Quiz5', questions=[{'id': 'q1', 'type': 'texte'}])
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'x'})
        other_enquete = services.creer_enquete(
            other, titre='AutreQuiz', questions=[{'id': 'q1', 'type': 'texte'}])
        self.assertEqual(len(services.participations_enquete(other_enquete)), 0)

    def test_endpoint_export_xlsx(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        enquete = services.creer_enquete(
            self.co, titre='Quiz6', questions=[{'id': 'q1', 'type': 'texte'}])
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'x'})
        user = User.objects.create_user(
            username='zmkt13-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(
            f'/api/django/compta/enquetes/{enquete.id}/resultats/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
