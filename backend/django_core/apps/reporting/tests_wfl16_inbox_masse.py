"""WFL16-INBOX — l'approbation groupée de l'inbox (``decider-en-masse/``)
route désormais les items ``source='workflow'`` via
``core.workflow.approuver_en_masse`` (NTWFL16) au lieu de les décider un par
un : la boucle historique n'appliquait AUCUNE garde de cohorte (même type
d'objet + même palier), alors que ``approuver_en_masse`` la refuse
explicitement (``ValueError``) sur une sélection hétérogène.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import workflow as core_workflow
from core.models import (
    WorkflowDefinition, WorkflowStepDefinition, WorkflowStepInstance,
)

User = get_user_model()
URL_MASSE = '/api/django/reporting/approbations-en-attente/decider-en-masse/'
NOW = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0, 0))


def _definition(company, code, nb_etapes=2):
    wf = WorkflowDefinition.objects.create(company=company, code=code, nom=code)
    for i in range(1, nb_etapes + 1):
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=i, nom=f'Palier {i}')
    return wf


class Wfl16InboxMasseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='wfl16-inbox-co', defaults={'nom': 'WFL16 Inbox Co'})[0]
        self.user = User.objects.create_user(
            username='wfl16_inbox_u', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        # Cibles générique du MÊME type (Company, fondation) — même patron
        # que core/tests/test_ntwfl16_approbation_groupee.py.
        self.cibles = [
            Company.objects.get_or_create(
                slug=f'wfl16-inbox-cible-{i}',
                defaults={'nom': f'Cible {i}'})[0]
            for i in range(3)
        ]

    def _steps_meme_cohorte(self, n=3):
        wf = _definition(self.company, 'wfl16-inbox-meme')
        instances = [
            core_workflow.demarrer_workflow(
                wf, cible, self.company, now=NOW)
            for cible in self.cibles[:n]
        ]
        return [core_workflow.etape_courante_de(i) for i in instances]

    def test_approbation_groupee_de_meme_cohorte_decide_tout(self):
        steps = self._steps_meme_cohorte(3)
        resp = self.api.post(URL_MASSE, {
            'items': [{'source': 'workflow', 'id': s.id} for s in steps],
            'decision': 'approuver', 'motif': 'Lot validé',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = resp.data['resultats']
        self.assertEqual(len(resultats), 3)
        self.assertTrue(all(r['ok'] for r in resultats))
        approuvees = WorkflowStepInstance.objects.filter(
            pk__in=[s.pk for s in steps],
            statut=WorkflowStepInstance.STATUT_APPROUVE,
            commentaire='Lot validé')
        self.assertEqual(approuvees.count(), 3)

    def test_cohorte_melangee_est_refusee_avec_un_motif(self):
        # Deux définitions DIFFÉRENTES (donc deux paliers/instances non
        # interchangeables) sélectionnées dans le MÊME lot : la garde de
        # cohorte de `approuver_en_masse` doit refuser tout le sous-lot.
        wf_a = _definition(self.company, 'wfl16-inbox-a')
        wf_b = _definition(self.company, 'wfl16-inbox-b', nb_etapes=3)
        step_a = core_workflow.etape_courante_de(
            core_workflow.demarrer_workflow(
                wf_a, self.cibles[0], self.company, now=NOW))
        step_b = core_workflow.etape_courante_de(
            core_workflow.demarrer_workflow(
                wf_b, self.cibles[1], self.company, now=NOW))
        # `cohorte_approbation` clé sur (content_type, ordre) : les deux
        # cibles sont bien deux `Company` (même content_type) au palier 1,
        # donc identiques SAUF si les définitions divergent sur autre chose
        # qu'ordre — pour garantir des cohortes distinctes, on force un
        # palier différent en avançant l'une des deux instances.
        core_workflow.decide_step(step_a, approve=True, now=NOW)
        step_a = core_workflow.etape_courante_de(step_a.instance)

        resp = self.api.post(URL_MASSE, {
            'items': [
                {'source': 'workflow', 'id': step_a.id},
                {'source': 'workflow', 'id': step_b.id},
            ],
            'decision': 'approuver', 'motif': '',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = resp.data['resultats']
        self.assertEqual(len(resultats), 2)
        self.assertTrue(all(not r['ok'] for r in resultats))
        for r in resultats:
            self.assertTrue(r['detail'])  # motif explicite, jamais vide
        # Aucune des deux étapes n'a bougé (tout-ou-rien du sous-lot).
        step_a.refresh_from_db()
        step_b.refresh_from_db()
        self.assertEqual(step_a.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
        self.assertEqual(step_b.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)

    def test_refuser_ne_passe_pas_par_approuver_en_masse(self):
        # Décision 'refuser' : chemin historique préservé (approuver_en_masse
        # ne couvre pas le refus).
        steps = self._steps_meme_cohorte(2)
        resp = self.api.post(URL_MASSE, {
            'items': [{'source': 'workflow', 'id': s.id} for s in steps],
            'decision': 'refuser', 'motif': 'Motif de refus',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(all(r['ok'] for r in resp.data['resultats']))
        for step in steps:
            step.refresh_from_db()
            self.assertEqual(step.statut, WorkflowStepInstance.STATUT_REJETE)

    def test_item_introuvable_est_signale(self):
        resp = self.api.post(URL_MASSE, {
            'items': [{'source': 'workflow', 'id': 999999}],
            'decision': 'approuver', 'motif': '',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['resultats'], [{
            'source': 'workflow', 'id': 999999, 'ok': False,
            'detail': 'Introuvable.',
        }])
