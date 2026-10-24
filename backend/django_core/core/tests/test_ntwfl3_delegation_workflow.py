"""Tests NTWFL3 — délégation de vacances (XKB3) étendue au moteur BPM.

Couvre :
- ``core.workflow.register_delegation_resolver`` / ``delegants_actifs_pour``
  (registre pur : ``core`` ne connaît jamais ``apps.automation``).
- ``core.selectors.delegants_actifs_pour`` (adaptateur mince).
- ``core.workflow.decide_step(..., on_behalf_of=...)`` journalise la
  décision « au nom de » dans le commentaire existant (aucune nouvelle
  colonne) ; ``on_behalf_of=None`` (défaut) laisse le comportement
  historique STRICTEMENT inchangé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import selectors as core_selectors
from core import workflow
from core.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition,
    WorkflowStepInstance)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def _make_instance(company):
    wf = WorkflowDefinition.objects.create(
        company=company, code='ntwfl3', nom='NTWFL3')
    WorkflowStepDefinition.objects.create(
        definition=wf, ordre=1, nom='Étape 1')
    return workflow.demarrer_workflow(wf, company, company)


class RegistreDelegationTests(TestCase):
    def tearDown(self):
        # Ne laisse jamais un résolveur de test fuiter vers un autre test.
        workflow.register_delegation_resolver(None)

    def test_sans_resolveur_liste_vide(self):
        workflow.register_delegation_resolver(None)
        self.assertEqual(workflow.delegants_actifs_pour(object(), object()), [])

    def test_resolveur_enregistre_est_appele(self):
        appels = []

        def resolveur(suppleant, company, at=None):
            appels.append((suppleant, company, at))
            return [42]

        workflow.register_delegation_resolver(resolveur)
        resultat = workflow.delegants_actifs_pour('sup', 'co', at='now')
        self.assertEqual(resultat, [42])
        self.assertEqual(appels, [('sup', 'co', 'now')])

    def test_resolveur_qui_leve_ne_casse_jamais(self):
        def resolveur(suppleant, company, at=None):
            raise RuntimeError('boom')

        workflow.register_delegation_resolver(resolveur)
        self.assertEqual(workflow.delegants_actifs_pour('sup', 'co'), [])

    def test_selector_delegue_au_registre(self):
        workflow.register_delegation_resolver(
            lambda suppleant, company, at=None: [7])
        self.assertEqual(
            core_selectors.delegants_actifs_pour('sup', 'co'), [7])


class DecideStepOnBehalfOfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl3-decide', 'NTWFL3 Decide')
        cls.suppleant = make_user(cls.company, 'ntwfl3-sup')
        # APAR46 — la décision « au nom de » vaut le palier du DÉLÉGANT.
        cls.delegant = User.objects.create_user(
            username='ntwfl3-del', password='x', company=cls.company,
            role_legacy='responsable')

    def test_sans_on_behalf_of_comportement_inchange(self):
        instance = _make_instance(self.company)
        step = workflow.etape_courante_de(instance)
        decide = workflow.decide_step(step, approve=True, commentaire='OK')
        self.assertEqual(decide.commentaire, 'OK')

    def test_avec_on_behalf_of_journalise_au_nom_de(self):
        instance = _make_instance(self.company)
        step = workflow.etape_courante_de(instance)
        decide = workflow.decide_step(
            step, approve=True, user=self.suppleant,
            commentaire='RAS', on_behalf_of=self.delegant)
        self.assertIn(f'au nom de {self.delegant}', decide.commentaire)
        self.assertIn('RAS', decide.commentaire)
        self.assertEqual(decide.assignee_id, self.suppleant.id)

    def test_rejet_avec_on_behalf_of(self):
        instance = _make_instance(self.company)
        step = workflow.etape_courante_de(instance)
        decide = workflow.decide_step(
            step, approve=False, user=self.suppleant,
            on_behalf_of=self.delegant)
        self.assertIn(f'au nom de {self.delegant}', decide.commentaire)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, instance.STATUT_TERMINE)


class SeparationDemandeurTests(TestCase):
    """APAR76 — le Responsable qui démarre un workflow ne décide pas sa
    propre étape (séparation des tâches) ; un second Responsable, oui."""

    URL = '/api/django/reporting/approbations-en-attente/decider/'
    MOTIF = ('Vous ne pouvez pas approuver votre propre demande '
             '(séparation des tâches).')

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('apar76-sod', 'APAR76 SOD')
        cls.demarreur = User.objects.create_user(
            username='apar76-demarreur', password='x', company=cls.company,
            role_legacy='responsable')
        cls.second = User.objects.create_user(
            username='apar76-second', password='x', company=cls.company,
            role_legacy='responsable')

    def _decider(self, user, step):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client.post(self.URL, {
            'source': 'workflow', 'id': step.pk, 'decision': 'approuver',
        }, format='json')

    def test_demarreur_ne_decide_pas_sa_propre_etape(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='apar76', nom='APAR76')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape 1')
        instance = workflow.demarrer_workflow(
            wf, self.company, self.company, user=self.demarreur)
        step = workflow.etape_courante_de(instance)

        resp = self._decider(self.demarreur, step)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data['detail'], self.MOTIF)

        rapport = workflow.approuver_en_masse([step], user=self.demarreur)
        self.assertEqual(rapport['decisions'], [])
        self.assertEqual(
            rapport['exclusions'], [{'step_id': step.pk, 'motif': self.MOTIF}])

        relue = WorkflowStepInstance.objects.get(pk=step.pk)
        self.assertEqual(relue.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
        self.assertIsNone(relue.assignee_id)
        instance_relue = WorkflowInstance.objects.get(pk=instance.pk)
        self.assertEqual(instance_relue.statut, WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(instance_relue.demandeur_id, self.demarreur.pk)

        resp = self._decider(self.second, step)
        self.assertEqual(resp.status_code, 200, resp.data)
        relue = WorkflowStepInstance.objects.get(pk=step.pk)
        self.assertEqual(relue.statut, WorkflowStepInstance.STATUT_APPROUVE)
        self.assertEqual(relue.assignee_id, self.second.pk)
