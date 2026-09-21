"""NTGRC22 — questionnaires de conformité fournisseurs.

Garanties : compléter TOUTES les réponses fait passer le questionnaire à
« complété » et le score agrège les conformes ; ``conforme`` reste à trois
états (vide ≠ non conforme) ; ``statut``/``score`` ne s'écrivent pas au champ ;
tout est scopé société.
"""
import json
from pathlib import Path

from django.test import TestCase

from apps.grc.models import QuestionnaireFournisseur, ReponseQuestionnaire
from apps.grc.services import (
    TransitionQuestionnaireInterdite, changer_statut_questionnaire,
    recalculer_questionnaire,
)
from authentication.models import Company
from testkit.base import TenantAPITestCase


class RecalculQuestionnaireTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC22 SA', slug='ntgrc22')

    def _questionnaire(self, **kw):
        return QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='7', **kw)

    def _question(self, questionnaire, ordre, **kw):
        return ReponseQuestionnaire.objects.create(
            company=self.company, questionnaire=questionnaire, ordre=ordre,
            question=f'Question {ordre}', **kw)

    def test_completer_toutes_les_reponses_passe_a_complete(self):
        questionnaire = self._questionnaire()
        for i in (1, 2, 3):
            self._question(questionnaire, i, reponse='oui', conforme=True)
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_COMPLETE)
        self.assertEqual(questionnaire.score, 100)

    def test_le_score_agrege_les_conformes_sur_le_total(self):
        questionnaire = self._questionnaire()
        self._question(questionnaire, 1, reponse='oui', conforme=True)
        self._question(questionnaire, 2, reponse='oui', conforme=True)
        self._question(questionnaire, 3, reponse='non', conforme=False)
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.score, 67)

    def test_une_question_non_evaluee_n_est_pas_un_ecart(self):
        """`conforme=None` ne compte NI comme conforme NI comme non conforme."""
        questionnaire = self._questionnaire()
        self._question(questionnaire, 1, reponse='oui', conforme=True)
        question = self._question(questionnaire, 2, reponse='peut-être')
        self.assertIsNone(question.conforme)
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.score, 50)

    def test_une_reponse_manquante_laisse_en_cours(self):
        questionnaire = self._questionnaire()
        self._question(questionnaire, 1, reponse='oui', conforme=True)
        self._question(questionnaire, 2)
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_EN_COURS)

    def test_une_question_facultative_ne_bloque_pas_la_completude(self):
        questionnaire = self._questionnaire()
        self._question(questionnaire, 1, reponse='oui', conforme=True)
        self._question(questionnaire, 2, obligatoire=False)
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_COMPLETE)

    def test_un_questionnaire_valide_n_est_jamais_retrograde(self):
        questionnaire = self._questionnaire(
            statut=QuestionnaireFournisseur.STATUT_VALIDE)
        self._question(questionnaire, 1)
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_VALIDE)

    def test_un_questionnaire_vide_ne_vaut_pas_complete(self):
        questionnaire = self._questionnaire()
        recalculer_questionnaire(questionnaire)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_ENVOYE)
        self.assertEqual(questionnaire.score, 0)


class TransitionQuestionnaireTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC22 T', slug='ntgrc22-t')

    def test_on_ne_valide_pas_un_questionnaire_non_complete(self):
        questionnaire = QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='1')
        with self.assertRaises(TransitionQuestionnaireInterdite):
            changer_statut_questionnaire(
                questionnaire, QuestionnaireFournisseur.STATUT_VALIDE)

    def test_complete_vers_valide(self):
        questionnaire = QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='1',
            statut=QuestionnaireFournisseur.STATUT_COMPLETE)
        changer_statut_questionnaire(
            questionnaire, QuestionnaireFournisseur.STATUT_VALIDE)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_VALIDE)

    def test_un_statut_inconnu_est_refuse(self):
        questionnaire = QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='1')
        with self.assertRaises(TransitionQuestionnaireInterdite):
            changer_statut_questionnaire(questionnaire, 'archive')


class EndpointQuestionnaireTests(TenantAPITestCase):
    BASE = '/api/django/grc/questionnaires-fournisseur/'
    REPONSES = '/api/django/grc/reponses-questionnaire/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe_et_le_statut(self):
        r = self._admin().post(
            self.BASE, {'type': 'rgpd', 'statut': 'valide', 'score': 99},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        questionnaire = QuestionnaireFournisseur.objects.get(pk=r.data['id'])
        self.assertEqual(questionnaire.company, self.company)
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_ENVOYE)
        self.assertEqual(questionnaire.score, 0)

    def test_repondre_par_endpoint_recalcule_le_questionnaire(self):
        questionnaire = QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='')
        r = self._admin().post(
            self.REPONSES,
            {'questionnaire': questionnaire.pk, 'ordre': 1,
             'question': 'Hébergement ?', 'reponse': 'Maroc',
             'conforme': True},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.statut,
                         QuestionnaireFournisseur.STATUT_COMPLETE)
        self.assertEqual(questionnaire.score, 100)

    def test_changer_statut_nomme_le_champ_en_cas_de_refus(self):
        questionnaire = QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='')
        r = self._admin().post(
            f'{self.BASE}{questionnaire.pk}/changer-statut/',
            {'statut': 'valide'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('statut', r.data)

    def test_un_fournisseur_inconnu_est_refuse(self):
        r = self._admin().post(
            self.BASE, {'fournisseur_ref': '999999'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('fournisseur_ref', r.data)

    def test_liste_scopee_societe(self):
        QuestionnaireFournisseur.objects.create(
            company=self.other_company, fournisseur_ref='1')
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])

    def test_on_ne_repond_pas_au_questionnaire_d_une_autre_societe(self):
        etranger = QuestionnaireFournisseur.objects.create(
            company=self.other_company, fournisseur_ref='1')
        r = self._admin().post(
            self.REPONSES,
            {'questionnaire': etranger.pk, 'question': 'X'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('questionnaire', r.data)


class ContratPartageTests(TestCase):
    """PACT10 — l'exemple partagé colle au contrat réel du serveur.

    NTESG8/NTESG17 branchent leur collecte ESG sur CE moteur : si l'exemple
    et le sérialiseur divergent, les deux moitiés repartent en aveugle — c'est
    exactement l'incident du 03/08/2026.
    """

    CHEMIN = (Path(__file__).resolve().parents[1] / 'contract_samples'
              / 'questionnaires_fournisseur.json')

    def test_l_exemple_porte_les_memes_cles_que_le_serialiseur(self):
        from apps.grc.serializers import QuestionnaireFournisseurSerializer

        exemple = json.loads(self.CHEMIN.read_text(encoding='utf-8'))
        attendues = set(
            QuestionnaireFournisseurSerializer.Meta.fields)
        self.assertEqual(set(exemple['exemple']), attendues)

    def test_l_exemple_de_reponse_porte_les_memes_cles(self):
        from apps.grc.serializers import ReponseQuestionnaireSerializer

        exemple = json.loads(self.CHEMIN.read_text(encoding='utf-8'))
        attendues = set(ReponseQuestionnaireSerializer.Meta.fields)
        for ligne in exemple['exemple_reponses']['results']:
            self.assertEqual(set(ligne), attendues)

    def test_conforme_reste_a_trois_etats_dans_l_exemple(self):
        exemple = json.loads(self.CHEMIN.read_text(encoding='utf-8'))
        valeurs = {ligne['conforme']
                   for ligne in exemple['exemple_reponses']['results']}
        self.assertIn(True, valeurs)
        self.assertIn(False, valeurs)
