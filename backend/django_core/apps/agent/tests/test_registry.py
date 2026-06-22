"""AG1 — Tests du registre d'actions agentiques.

Couvre :
- :class:`AgentAction` valide ses champs (risk autorisé, key obligatoire) ;
- :func:`register` est unique (refuse une key en double) ;
- :func:`for_user` filtre par permission ERP (rôle de la société) ;
- un superuser voit tout, un anonyme rien, une action sans permission est
  ouverte à tout authentifié.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.roles.models import Role
from apps.agent.registry import (
    AgentAction, RISK_INTERNAL, RISK_OUTWARD, register, unregister,
    all_actions, for_user,
)

User = get_user_model()


class AgentActionDataclassTest(TestCase):
    def test_invalid_risk_rejected(self):
        with self.assertRaises(ValueError):
            AgentAction(key='k', label='L', description='d',
                        endpoint='/x/', risk='bogus')

    def test_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            AgentAction(key='', label='L', description='d', endpoint='/x/')

    def test_as_dict_shape(self):
        a = AgentAction(
            key='demo.read', label='Lire', description='Lit un truc',
            endpoint='/api/x/', method='get', required_permission='stock_voir',
            risk=RISK_OUTWARD, confirm_summary='résumé')
        d = a.as_dict()
        self.assertEqual(d['key'], 'demo.read')
        self.assertEqual(d['method'], 'GET')  # normalisé en majuscules
        self.assertEqual(d['required_permission'], 'stock_voir')
        self.assertEqual(d['risk'], RISK_OUTWARD)
        self.assertEqual(d['confirm_summary'], 'résumé')


class RegisterUniquenessTest(TestCase):
    def tearDown(self):
        unregister('tmp.unique')

    def test_duplicate_key_rejected(self):
        a = AgentAction(key='tmp.unique', label='X', description='d',
                        endpoint='/x/')
        register(a)
        try:
            with self.assertRaises(ValueError):
                register(AgentAction(key='tmp.unique', label='Y',
                                     description='d2', endpoint='/y/'))
        finally:
            unregister('tmp.unique')

    def test_register_appears_in_all_actions(self):
        register(AgentAction(key='tmp.unique', label='X', description='d',
                             endpoint='/x/', risk=RISK_INTERNAL))
        keys = [a.key for a in all_actions()]
        self.assertIn('tmp.unique', keys)


class ForUserFilterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Agent Co', slug='agent-co')
        # Rôle « lecture seule » : ne porte que crm_voir.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='ro', password='x', role=self.readonly_role,
            company=self.company)
        # Rôle « vendeur » : peut créer des devis + PDF.
        self.sales_role = Role.objects.create(
            company=self.company, nom='Vendeur',
            permissions=['ventes_creer', 'ventes_pdf', 'crm_voir'])
        self.sales = User.objects.create_user(
            username='sales', password='x', role=self.sales_role,
            company=self.company)
        self.superuser = User.objects.create_superuser(
            username='root', password='x')

    def test_readonly_user_sees_only_permitted(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertIn('crm.lead.list', keys)            # crm_voir → autorisé
        self.assertNotIn('ventes.devis.create', keys)   # ventes_creer manquant
        self.assertNotIn('ventes.devis.proposal_pdf', keys)
        self.assertNotIn('stock.produit.delete', keys)

    def test_sales_user_sees_sales_actions(self):
        keys = {a.key for a in for_user(self.sales)}
        self.assertIn('ventes.devis.create', keys)
        self.assertIn('ventes.devis.proposal_pdf', keys)
        self.assertIn('crm.lead.list', keys)
        self.assertNotIn('stock.produit.delete', keys)  # stock_supprimer manquant

    def test_superuser_sees_everything(self):
        keys = {a.key for a in for_user(self.superuser)}
        builtin = {a.key for a in all_actions()}
        self.assertTrue(builtin.issubset(keys))

    def test_action_without_permission_open_to_authenticated(self):
        a = AgentAction(key='tmp.open', label='Ouvert', description='d',
                        endpoint='/open/', required_permission=None)
        register(a)
        try:
            self.assertIn('tmp.open', {x.key for x in for_user(self.readonly)})
        finally:
            unregister('tmp.open')

    def test_anonymous_sees_nothing(self):
        class _Anon:
            is_authenticated = False
        self.assertEqual(for_user(_Anon()), [])
        self.assertEqual(for_user(None), [])


class GuardedWriteActionsTest(TestCase):
    """FG351 — les écritures en langage naturel (Devis/Lead/Client) sont des
    actions GARDÉES : risk=outward (=> propose→confirm côté relais) et gatées
    par une permission ERP (jamais exécutées en lecture seule)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Write Co', slug='write-co')
        # Rôle « lecture seule » : crm_voir uniquement (aucun droit d'écriture).
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='wro', password='x', role=self.readonly_role,
            company=self.company)
        # Rôle « commercial » : crm_creer + ventes_creer → peut proposer toutes
        # les créations.
        self.writer_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_creer', 'ventes_creer'])
        self.writer = User.objects.create_user(
            username='wwr', password='x', role=self.writer_role,
            company=self.company)

    def _by_key(self):
        return {a.key: a for a in all_actions()}

    def test_three_write_actions_registered(self):
        catalogue = self._by_key()
        for key in ('ventes.devis.create', 'crm.client.create',
                    'crm.lead.create'):
            self.assertIn(key, catalogue)

    def test_write_actions_are_guarded_outward(self):
        catalogue = self._by_key()
        for key in ('ventes.devis.create', 'crm.client.create',
                    'crm.lead.create'):
            action = catalogue[key]
            # outward => le relais renvoie une PROPOSITION à confirmer (jamais
            # une exécution immédiate).
            self.assertEqual(action.risk, RISK_OUTWARD, key)
            self.assertEqual(action.method.upper(), 'POST', key)
            self.assertTrue(action.confirm_summary, key)

    def test_write_actions_gated_by_permission(self):
        catalogue = self._by_key()
        self.assertEqual(
            catalogue['crm.client.create'].required_permission, 'crm_creer')
        self.assertEqual(
            catalogue['crm.lead.create'].required_permission, 'crm_creer')
        self.assertEqual(
            catalogue['ventes.devis.create'].required_permission,
            'ventes_creer')

    def test_readonly_cannot_propose_writes(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertNotIn('crm.client.create', keys)
        self.assertNotIn('crm.lead.create', keys)
        self.assertNotIn('ventes.devis.create', keys)

    def test_writer_can_propose_writes(self):
        keys = {a.key for a in for_user(self.writer)}
        self.assertIn('crm.client.create', keys)
        self.assertIn('crm.lead.create', keys)
        self.assertIn('ventes.devis.create', keys)

    def test_client_and_lead_require_nom(self):
        catalogue = self._by_key()
        for key in ('crm.client.create', 'crm.lead.create'):
            self.assertIn('nom', catalogue[key].inputs.get('required', []), key)
