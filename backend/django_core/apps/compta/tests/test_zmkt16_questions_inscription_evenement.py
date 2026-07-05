"""ZMKT16 — Questions d'inscription par événement (capture de données à
l'inscription).

Couvre : définir des questions obligatoires/optionnelles, l'inscription
publique refuse la soumission sans réponse obligatoire, les réponses sont
lisibles sur l'inscription et reportées sur le lead, migration additive,
tests.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EvenementMarketing, QuestionEvenement


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class QuestionsInscriptionEvenementTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt16', 'ZMKT16')
        self.evt = EvenementMarketing.objects.create(
            company=self.co, nom='Salon', date_debut=timezone.now())

    def test_definir_questions_obligatoires_optionnelles(self):
        QuestionEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Intéressé pompage ?',
            type_question=QuestionEvenement.Type.BOOLEEN, obligatoire=True)
        QuestionEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Commentaire',
            obligatoire=False)
        self.assertEqual(self.evt.questions.count(), 2)

    def test_refuse_sans_reponse_obligatoire(self):
        question = QuestionEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Q obligatoire',
            obligatoire=True)
        with self.assertRaises(ValueError):
            services.inscrire_evenement(self.evt, nom='Sans réponse')
        # Avec la réponse fournie -> pas d'erreur.
        inscription = services.inscrire_evenement(
            self.evt, nom='Avec réponse',
            reponses_questions={str(question.id): 'oui'})
        self.assertIsNotNone(inscription.id)

    def test_reponses_lisibles_sur_inscription(self):
        question = QuestionEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Intéressé pompage ?')
        inscription = services.inscrire_evenement(
            self.evt, nom='Karim',
            reponses_questions={str(question.id): 'oui'})
        self.assertEqual(
            inscription.reponses_questions[str(question.id)], 'oui')

    def test_pas_de_questions_comportement_actuel(self):
        inscription = services.inscrire_evenement(self.evt, nom='SansQuestion')
        self.assertEqual(inscription.reponses_questions, {})

    def test_endpoint_inscription_refuse_sans_reponse(self):
        QuestionEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Obligatoire',
            obligatoire=True)
        resp = self.client.post(
            f'/api/django/compta/evenements-marketing/{self.evt.id}/'
            'inscription-publique/',
            data={'nom': 'Test'}, content_type='application/json')
        self.assertEqual(resp.status_code, 400)
