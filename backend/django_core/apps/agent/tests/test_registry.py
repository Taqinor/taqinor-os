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
