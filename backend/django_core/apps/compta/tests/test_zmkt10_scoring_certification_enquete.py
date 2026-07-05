"""ZMKT10 — Scoring d'enquête + mode certification + score requis.

Couvre : un répondant au-dessus du seuil est marqué réussi et reçoit un
certificat PDF, en dessous échoué sans certificat, le mode sans-scoring
n'affiche aucun score, migration additive, tests (calcul score, seuil,
présence certificat).
"""
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Enquete


QUESTIONS_SCOREES = [
    {'id': 'q1', 'type': 'choix', 'libelle': 'Q1', 'options': ['a', 'b'],
     'points': 10, 'bonne_reponse': 'a'},
    {'id': 'q2', 'type': 'choix', 'libelle': 'Q2', 'options': ['a', 'b'],
     'points': 10, 'bonne_reponse': 'b'},
]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ScoringCertificationEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt10', 'ZMKT10')

    def test_calcul_score_toutes_bonnes(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz', questions=QUESTIONS_SCOREES)
        score = services.calculer_score_enquete(
            enquete, {'q1': 'a', 'q2': 'b'})
        self.assertEqual(float(score), 100.0)

    def test_calcul_score_partiel(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz2', questions=QUESTIONS_SCOREES)
        score = services.calculer_score_enquete(
            enquete, {'q1': 'a', 'q2': 'a'})
        self.assertEqual(float(score), 50.0)

    def test_reussi_au_dessus_du_seuil(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz3', questions=QUESTIONS_SCOREES)
        enquete.mode_scoring = Enquete.ModeScoring.AVEC_REPONSES
        enquete.score_requis_pct = 50
        enquete.save(update_fields=['mode_scoring', 'score_requis_pct'])
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'a', 'q2': 'b'})
        self.assertTrue(reponse.reussi)
        self.assertEqual(float(reponse.score_pct), 100.0)

    def test_echoue_sous_le_seuil_sans_certificat(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz4', questions=QUESTIONS_SCOREES)
        enquete.mode_scoring = Enquete.ModeScoring.AVEC_REPONSES
        enquete.score_requis_pct = 80
        enquete.est_certification = True
        enquete.save(update_fields=[
            'mode_scoring', 'score_requis_pct', 'est_certification'])
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'a', 'q2': 'a'})
        self.assertFalse(reponse.reussi)
        self.assertFalse(reponse.certificat_genere)

    def test_certificat_genere_si_reussi_et_certification(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz5', questions=QUESTIONS_SCOREES)
        enquete.mode_scoring = Enquete.ModeScoring.AVEC_REPONSES
        enquete.score_requis_pct = 50
        enquete.est_certification = True
        enquete.save(update_fields=[
            'mode_scoring', 'score_requis_pct', 'est_certification'])
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'a', 'q2': 'b'})
        self.assertTrue(reponse.certificat_genere)

    def test_mode_sans_scoring_pas_de_score(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz6', questions=QUESTIONS_SCOREES)
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'a', 'q2': 'b'})
        self.assertIsNone(reponse.score_pct)
        self.assertIsNone(reponse.reussi)

    @patch('apps.compta.pdf_certificat_enquete._html_to_pdf')
    def test_generer_certificat_pdf_appelle_weasyprint(self, mock_pdf):
        mock_pdf.return_value = b'%PDF-FAKE'
        enquete = services.creer_enquete(
            self.co, titre='Quiz7', questions=QUESTIONS_SCOREES)
        enquete.mode_scoring = Enquete.ModeScoring.AVEC_REPONSES
        enquete.score_requis_pct = 50
        enquete.est_certification = True
        enquete.save(update_fields=[
            'mode_scoring', 'score_requis_pct', 'est_certification'])
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'a', 'q2': 'b'})
        pdf_bytes = services.generer_certificat_pdf(reponse)
        self.assertEqual(pdf_bytes, b'%PDF-FAKE')

    def test_generer_certificat_pdf_none_si_pas_certifie(self):
        enquete = services.creer_enquete(
            self.co, titre='Quiz8', questions=QUESTIONS_SCOREES)
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'a', 'q2': 'b'})
        self.assertIsNone(services.generer_certificat_pdf(reponse))
