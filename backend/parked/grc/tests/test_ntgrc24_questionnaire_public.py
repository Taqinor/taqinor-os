"""NTGRC24 — portail PUBLIC de réponse au questionnaire fournisseur.

Garanties : un fournisseur SANS COMPTE soumet ses réponses via un jeton
opaque, le questionnaire passe « complété », l'horodatage et l'IP sont posés
CÔTÉ SERVEUR (horloge figée), un lien expiré ne répond plus, et aucun accès
inter-tenant n'est possible (le jeton est la seule clé).
"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.grc.models import ModeleQuestionnaire, QuestionnaireFournisseur
from apps.grc.services import (
    LienQuestionnaireInvalide, emettre_lien_questionnaire,
    instancier_questionnaire, questionnaire_par_token,
)
from authentication.models import Company
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 08:00:00+00:00'
PLUS_TARD = '2026-11-30 08:00:00+00:00'


def _questionnaire(company, questions=('Q1', 'Q2')):
    modele = ModeleQuestionnaire.objects.create(
        company=company, code='M1', nom='Trame',
        questions=[{'intitule': q} for q in questions])
    return instancier_questionnaire(modele, '')


class PortailPublicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC24 SA', slug='ntgrc24')

    def setUp(self):
        super().setUp()
        cache.clear()  # remet à zéro le throttle anonyme entre tests
        self.client = APIClient()
        self.questionnaire = _questionnaire(self.company)
        with frozen(INSTANT):
            emettre_lien_questionnaire(self.questionnaire, jours=30)
        self.url = ('/api/django/grc/public/questionnaire/'
                    f'{self.questionnaire.token_acces}/')

    def test_lecture_publique_sans_compte(self):
        with frozen(INSTANT):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['questions']), 2)
        self.assertEqual(r.data['questions'][0]['ordre'], 1)
        self.assertEqual(r.data['statut'],
                         QuestionnaireFournisseur.STATUT_ENVOYE)

    def test_la_vue_publique_n_expose_ni_score_ni_evaluateur(self):
        with frozen(INSTANT):
            r = self.client.get(self.url)
        self.assertNotIn('score', r.data)
        self.assertNotIn('evaluateur', r.data)
        self.assertNotIn('fournisseur_ref', r.data)
        self.assertNotIn('id', r.data)
        self.assertNotIn('conforme', r.data['questions'][0])

    def test_soumission_complete_passe_le_questionnaire_a_complete(self):
        with frozen(INSTANT):
            r = self.client.post(
                self.url,
                {'reponses': [
                    {'ordre': 1, 'reponse': 'Casablanca'},
                    {'ordre': 2, 'reponse': 'Oui'},
                ]},
                format='json', REMOTE_ADDR='41.250.1.9')
        self.assertEqual(r.status_code, 200, r.content)
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_COMPLETE)
        self.assertEqual(
            self.questionnaire.date_soumission.isoformat(),
            '2026-09-12T08:00:00+00:00')
        self.assertEqual(self.questionnaire.preuve_soumission['ip'],
                         '41.250.1.9')
        self.assertEqual(
            self.questionnaire.preuve_soumission['canal'],
            'portail_fournisseur')

    def test_soumission_partielle_reste_en_cours(self):
        with frozen(INSTANT):
            self.client.post(
                self.url, {'reponses': [{'ordre': 1, 'reponse': 'Oui'}]},
                format='json')
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_EN_COURS)

    def test_un_ordre_inconnu_ne_cree_aucune_question(self):
        with frozen(INSTANT):
            self.client.post(
                self.url,
                {'reponses': [{'ordre': 99, 'reponse': 'Injection'}]},
                format='json')
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.reponses.count(), 2)

    def test_le_fournisseur_n_ecrit_jamais_conforme(self):
        with frozen(INSTANT):
            self.client.post(
                self.url,
                {'reponses': [
                    {'ordre': 1, 'reponse': 'Oui', 'conforme': True},
                    {'ordre': 2, 'reponse': 'Oui', 'conforme': True},
                ]},
                format='json')
        self.questionnaire.refresh_from_db()
        self.assertEqual(
            [r.conforme for r in self.questionnaire.reponses.all()],
            [None, None])
        self.assertEqual(self.questionnaire.score, 0)

    def test_un_lien_expire_ne_repond_plus(self):
        with frozen(PLUS_TARD):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410)

    def test_un_jeton_inconnu_est_404(self):
        r = self.client.get(
            '/api/django/grc/public/questionnaire/jeton-bidon/')
        self.assertEqual(r.status_code, 404)

    def test_un_questionnaire_arbitre_n_est_plus_modifiable(self):
        self.questionnaire.statut = QuestionnaireFournisseur.STATUT_VALIDE
        self.questionnaire.save(update_fields=['statut'])
        with frozen(INSTANT):
            r = self.client.post(
                self.url, {'reponses': [{'ordre': 1, 'reponse': 'X'}]},
                format='json')
        self.assertEqual(r.status_code, 409)

    def test_un_corps_sans_liste_nomme_le_champ(self):
        with frozen(INSTANT):
            r = self.client.post(self.url, {'reponses': 'oui'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('reponses', r.data)

    def test_renouveler_le_lien_invalide_l_ancien(self):
        ancien = self.questionnaire.token_acces
        with frozen(INSTANT):
            emettre_lien_questionnaire(self.questionnaire, jours=15)
            with self.assertRaises(LienQuestionnaireInvalide):
                questionnaire_par_token(ancien)
        self.assertNotEqual(self.questionnaire.token_acces, ancien)


class LienPublicEndpointTests(TenantAPITestCase):
    BASE = '/api/django/grc/questionnaires-fournisseur/'

    def test_emettre_un_lien_public(self):
        questionnaire = _questionnaire(self.company)
        with frozen(INSTANT):
            r = self.client_as(role='admin').post(
                f'{self.BASE}{questionnaire.pk}/lien-public/',
                {'jours': 10}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        questionnaire.refresh_from_db()
        self.assertEqual(r.data['token'], questionnaire.token_acces)
        self.assertEqual(r.data['expire_le'], '2026-09-22T08:00:00+00:00')

    def test_le_lien_d_une_autre_societe_est_introuvable(self):
        etranger = _questionnaire(self.other_company)
        r = self.client_as(role='admin').post(
            f'{self.BASE}{etranger.pk}/lien-public/', {}, format='json')
        self.assertEqual(r.status_code, 404)
        etranger.refresh_from_db()
        self.assertIsNone(etranger.token_acces)
