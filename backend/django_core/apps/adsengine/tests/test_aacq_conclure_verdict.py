"""AACQ65 — La clôture d'expérience répond avec le verdict ENREGISTRÉ.

200 ``validated=<enregistré>`` si identique, 409 ``{detail, validated}`` si un
verdict contraire existe déjà — le posterior n'est jamais touché une seconde
fois. Forme comparée au contrat ``contract_samples/experience_conclure.json``.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import AssumptionNode, DecisionLog, Experiment

User = get_user_model()
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'experience_conclure.json')


class ConclureVerdictTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AACQ65', slug='aacq65')
        role = Role.objects.create(
            company=self.company, nom='aacq65-role',
            permissions=['adsengine_view', 'adsengine_manage'])
        user = User.objects.create_user(
            username='aacq65-u', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self.exp = Experiment.objects.create(
            company=self.company, name='Hook prix',
            status=Experiment.Statut.EN_COURS)
        self.node = AssumptionNode.objects.create(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Le hook prix marche mieux.', enjeux_s=0.5,
            pertinence_r=0.5, alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)
        DecisionLog.objects.create(
            company=self.company, experiment=self.exp,
            allocations={'winner_node_id': self.node.pk},
            summary_fr='Slot ouvert (VoI).')
        self.url = f'/api/django/adsengine/experiences/{self.exp.pk}/conclure/'

    def _conclure(self, validated):
        return self.api.post(self.url, {'validated': validated}, format='json')

    def _evidences(self):
        return DecisionLog.objects.filter(
            company=self.company,
            inputs__evidence_key=f'experiment:{self.exp.pk}:outcome').count()

    def _posterior(self):
        self.node.refresh_from_db()
        return (self.node.alpha, self.node.beta)

    def test_verdict_contraire_409_et_posterior_inchange(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        r1 = self._conclure(True)
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(set(r1.data), set(contrat['exemple']))
        self.assertIs(r1.data['validated'], True)
        self.assertEqual(self._posterior(), (2.0, 1.0))
        r2 = self._conclure(False)
        self.assertEqual(r2.status_code, 409, r2.data)
        self.assertEqual(set(r2.data), set(contrat['reponse_409']))
        self.assertEqual(
            r2.data['detail'],
            'Expérience déjà clôturée : hypothèse CONFIRMÉE — verdict '
            'inchangé.')
        self.assertIs(r2.data['validated'], True)
        self.assertEqual(self._posterior(), (2.0, 1.0))
        self.assertEqual(self._evidences(), 1)

    def test_reclore_identique_renvoie_verdict_enregistre(self):
        self._conclure(True)
        self._conclure(False)
        r3 = self._conclure(True)
        self.assertEqual(r3.status_code, 200, r3.data)
        self.assertIs(r3.data['validated'], True)
        self.assertIsNone(r3.data['decision_log'])
        self.assertEqual(self._posterior(), (2.0, 1.0))
        self.assertEqual(self._evidences(), 1)
