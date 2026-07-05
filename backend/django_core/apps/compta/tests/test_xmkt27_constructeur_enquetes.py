"""XMKT27 — Constructeur d'enquêtes avec logique conditionnelle + analytics.

Couvre : création d'une enquête à logique simple, réponse publique sans
auth, la conditionnelle s'applique, page résultats, tests.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Enquete, ReponseEnquete


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


QUESTIONS = [
    {'id': 'q1', 'type': 'choix', 'libelle': 'Avez-vous un projet solaire ?',
     'options': ['oui', 'non'], 'obligatoire': True},
    {'id': 'q2', 'type': 'texte', 'libelle': 'Précisez votre projet',
     'obligatoire': True, 'condition': {'question_id': 'q1', 'valeur': 'oui'}},
    {'id': 'q3', 'type': 'nps', 'libelle': 'Recommanderiez-vous ?',
     'obligatoire': False},
]


class ConstructeurEnquetesTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt27', 'XMKT27')

    def test_creation_enquete_logique_simple(self):
        enquete = services.creer_enquete(self.co, titre='Satisfaction', questions=QUESTIONS)
        self.assertTrue(enquete.token)
        self.assertEqual(len(enquete.questions), 3)

    def test_validation_type_inconnu_leve(self):
        with self.assertRaises(ValueError):
            services.valider_questions_enquete(
                [{'id': 'q1', 'type': 'inconnu'}])

    def test_validation_id_duplique_leve(self):
        with self.assertRaises(ValueError):
            services.valider_questions_enquete(
                [{'id': 'q1', 'type': 'texte'},
                 {'id': 'q1', 'type': 'choix'}])

    def test_conditionnelle_masque_question_si_condition_fausse(self):
        enquete = services.creer_enquete(self.co, titre='E', questions=QUESTIONS)
        visibles = services.questions_visibles(enquete, {'q1': 'non'})
        ids = [q['id'] for q in visibles]
        self.assertNotIn('q2', ids)
        self.assertIn('q1', ids)
        self.assertIn('q3', ids)

    def test_conditionnelle_affiche_question_si_condition_vraie(self):
        enquete = services.creer_enquete(self.co, titre='E2', questions=QUESTIONS)
        visibles = services.questions_visibles(enquete, {'q1': 'oui'})
        ids = [q['id'] for q in visibles]
        self.assertIn('q2', ids)

    def test_reponse_publique_sans_auth(self):
        enquete = services.creer_enquete(self.co, titre='E3', questions=QUESTIONS)
        resp = self.client.post(
            f'/api/django/compta/enquetes-publiques/{enquete.token}/soumettre/',
            data={'reponses': {'q1': 'non', 'q3': 8}}, content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(ReponseEnquete.objects.filter(enquete=enquete).count(), 1)

    def test_reponse_manquante_obligatoire_visible_refuse(self):
        enquete = services.creer_enquete(self.co, titre='E4', questions=QUESTIONS)
        with self.assertRaises(ValueError):
            services.soumettre_reponse_enquete(enquete, reponses={})

    def test_reponse_manquante_obligatoire_masquee_nest_pas_requise(self):
        enquete = services.creer_enquete(self.co, titre='E5', questions=QUESTIONS)
        # q2 obligatoire mais masquée (q1='non') → pas d'erreur malgré son absence.
        reponse = services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'non'})
        self.assertIsNotNone(reponse.id)

    def test_enquete_publique_endpoint_get(self):
        enquete = services.creer_enquete(self.co, titre='E6', questions=QUESTIONS)
        resp = self.client.get(
            f'/api/django/compta/enquetes-publiques/{enquete.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['titre'], 'E6')

    def test_enquete_publique_token_invalide_404(self):
        resp = self.client.get('/api/django/compta/enquetes-publiques/invalide/')
        self.assertEqual(resp.status_code, 404)

    def test_analytics_choix_repartition(self):
        enquete = services.creer_enquete(self.co, titre='E7', questions=QUESTIONS)
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'oui', 'q2': 'X'})
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'non'})
        analytics = services.analytics_enquete(enquete)
        self.assertEqual(analytics['q1']['repartition'], {'oui': 1, 'non': 1})

    def test_analytics_nps_consolide(self):
        enquete = services.creer_enquete(self.co, titre='E8', questions=QUESTIONS)
        services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'non', 'q3': 10})
        services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'non', 'q3': 3})
        analytics = services.analytics_enquete(enquete)
        self.assertIn('nps', analytics['q3'])

    def test_taux_completion(self):
        enquete = services.creer_enquete(self.co, titre='E9', questions=QUESTIONS)
        services.soumettre_reponse_enquete(enquete, reponses={'q1': 'non'})
        completion = services.taux_completion_enquete(enquete)
        self.assertEqual(completion['total'], 1)
        self.assertEqual(completion['taux_completion_pct'], 100.0)

    def test_reponses_visibles_sur_fiche_contact(self):
        enquete = services.creer_enquete(self.co, titre='E10', questions=QUESTIONS)
        services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'non'}, contact_ref='lead:42')
        reponse = ReponseEnquete.objects.get(enquete=enquete)
        self.assertEqual(reponse.contact_ref, 'lead:42')

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt27-b', 'XMKT27-B')
        services.creer_enquete(self.co, titre='E11', questions=QUESTIONS)
        self.assertEqual(Enquete.objects.filter(company=self.co).count(), 1)
        self.assertEqual(Enquete.objects.filter(company=other).count(), 0)
