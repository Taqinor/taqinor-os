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

from authentication.models import Company
from core import selectors as core_selectors
from core import workflow
from core.models import WorkflowDefinition, WorkflowStepDefinition

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
        cls.delegant = make_user(cls.company, 'ntwfl3-del')

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
