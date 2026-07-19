"""PUB2 — Actions LECTURE de « L'Arbre » sur ``noeuds-hypothese/`` :
``file-voi`` (classement VoI réel), ``<id>/tests`` (historique des décisions du
nœud), ``tests/<id>/leads`` (drill leads réels). Company-scopé + gaté
``adsengine_view``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import (
    AssumptionNode, DecisionLog, Experiment, ExperimentArm)

User = get_user_model()
BASE = '/api/django/adsengine/noeuds-hypothese/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_node(company, **kwargs):
    defaults = dict(
        company=company, classe=AssumptionNode.Classe.CREATIF,
        enonce_fr='Hypothèse.', enjeux_s=0.5, pertinence_r=0.5)
    defaults.update(kwargs)
    return AssumptionNode.objects.create(**defaults)


class FileVoiActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VoI Co', slug='voi-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(
            auth(nobody).get(f'{BASE}file-voi/').status_code, 403)

    def test_ranks_by_stakes_and_excludes_retired(self):
        high = make_node(
            self.company, enonce_fr='Enjeu fort', enjeux_s=0.9,
            pertinence_r=0.9)
        low = make_node(
            self.company, enonce_fr='Enjeu faible', enjeux_s=0.1,
            pertinence_r=0.1)
        make_node(
            self.company, enonce_fr='Retiré',
            statut=AssumptionNode.Statut.RETIRED)
        resp = auth(self.viewer).get(f'{BASE}file-voi/')
        self.assertEqual(resp.status_code, 200, resp.data)
        node_ids = [r['node_id'] for r in resp.data]
        # Le nœud retiré ne revient JAMAIS dans la file.
        self.assertEqual(set(node_ids), {high.pk, low.pk})
        # Classement RÉEL par S·U·R (U/T/C uniformes) : l'enjeu fort en tête.
        self.assertEqual(resp.data[0]['node_id'], high.pk)
        self.assertEqual(resp.data[0]['rang'], 1)
        self.assertGreater(resp.data[0]['voi'], resp.data[1]['voi'])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Autre', slug='autre-voi')
        make_node(other, enonce_fr='Nœud étranger', enjeux_s=0.9,
                  pertinence_r=0.9)
        resp = auth(self.viewer).get(f'{BASE}file-voi/')
        self.assertEqual(resp.data, [])


class NodeTestsActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tests Co', slug='tests-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.node = make_node(self.company, enonce_fr='Le hook facture gagne.')
        self.exp = Experiment.objects.create(
            company=self.company, name='Test hook facture',
            status=Experiment.Statut.EN_COURS)

    def _decision(self, company, exp, winner_pk, summary='Slot ouvert.'):
        return DecisionLog.objects.create(
            company=company, experiment=exp,
            allocations={'winner_node_id': winner_pk},
            summary_fr=summary)

    def test_returns_node_decision_history(self):
        self._decision(self.company, self.exp, self.node.pk,
                       summary='Le nœud facture ouvre un slot.')
        resp = auth(self.viewer).get(f'{BASE}{self.node.pk}/tests/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row['nom'], 'Test hook facture')
        self.assertIn('facture', row['verdict_display'])
        self.assertEqual(row['statut_display'], 'En cours')

    def test_ignores_decisions_for_other_nodes(self):
        other_node = make_node(self.company, enonce_fr='Autre nœud')
        self._decision(self.company, self.exp, other_node.pk)
        resp = auth(self.viewer).get(f'{BASE}{self.node.pk}/tests/')
        self.assertEqual(resp.data, [])

    def test_scoped_node_of_other_company_is_404(self):
        other = Company.objects.create(nom='Autre', slug='autre-t')
        foreign = make_node(other, enonce_fr='Étranger')
        resp = auth(self.viewer).get(f'{BASE}{foreign.pk}/tests/')
        self.assertEqual(resp.status_code, 404)


class TestLeadsActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Leads Co', slug='leads-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.exp = Experiment.objects.create(
            company=self.company, name='Exp leads',
            status=Experiment.Statut.EN_COURS)
        self.log = DecisionLog.objects.create(
            company=self.company, experiment=self.exp,
            allocations={'winner_node_id': 1}, summary_fr='x')

    def test_returns_leads_joined_on_arm_ad_id(self):
        from apps.crm.models import Lead

        ExperimentArm.objects.create(
            company=self.company, experiment=self.exp, ad_id='ad-123')
        Lead.objects.create(
            company=self.company, nom='Amine', ville='Casablanca',
            canal=Lead.Canal.META_ADS, meta_ad_id='ad-123')
        # Lead sur une autre ad → jamais rattaché à ce test.
        Lead.objects.create(
            company=self.company, nom='Autre', canal=Lead.Canal.META_ADS,
            meta_ad_id='ad-999')
        resp = auth(self.viewer).get(f'{BASE}tests/{self.log.pk}/leads/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['nom'], 'Amine')

    def test_no_arms_returns_empty(self):
        resp = auth(self.viewer).get(f'{BASE}tests/{self.log.pk}/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_other_company_decision_is_404(self):
        other = Company.objects.create(nom='Autre', slug='autre-l')
        other_exp = Experiment.objects.create(
            company=other, name='X', status=Experiment.Statut.EN_COURS)
        foreign_log = DecisionLog.objects.create(
            company=other, experiment=other_exp,
            allocations={'winner_node_id': 1}, summary_fr='x')
        resp = auth(self.viewer).get(
            f'{BASE}tests/{foreign_log.pk}/leads/')
        self.assertEqual(resp.status_code, 404)
