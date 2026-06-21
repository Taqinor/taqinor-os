"""AG7 — Tests des actions agentiques Stock.

Couvre :
  - les deux actions Stock (``ajuster_stock`` / ``brouillon_commande_
    fournisseur``) sont enregistrées dans le catalogue AG1 et exposées à un
    utilisateur qui porte la permission ERP requise ;
  - ``company`` n'apparaît jamais dans le schéma ``inputs`` (forcée serveur) ;
  - le mouvement de stock POSTé via l'endpoint relayé crée bien le mouvement
    avec la société forcée côté serveur (jamais depuis le corps).

Run :
    python manage.py test apps.stock.test_agent_actions -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import Produit, MouvementStock
from apps.stock.agent_actions import (
    AJUSTER_STOCK, BROUILLON_COMMANDE_FOURNISSEUR, register_stock_actions,
)
from apps.agent.registry import all_actions, for_user

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class StockAgentActionsCatalogueTest(TestCase):
    """Les actions Stock sont dans le catalogue et filtrées par permission."""

    def setUp(self):
        # ready() les enregistre déjà au démarrage ; idempotent ici aussi.
        register_stock_actions()
        self.company = Company.objects.create(nom='AG7 Co', slug='ag7-co')
        # Magasinier : porte stock_mouvement + stock_creer (les deux codes).
        self.magasinier_role = Role.objects.create(
            company=self.company, nom='Magasinier',
            permissions=['stock_voir', 'stock_creer', 'stock_mouvement'])
        self.magasinier = User.objects.create_user(
            username='ag7_mag', password='x', role=self.magasinier_role,
            company=self.company)
        # Lecture seule : ne porte que stock_voir → ne voit aucune des deux.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['stock_voir'])
        self.readonly = User.objects.create_user(
            username='ag7_ro', password='x', role=self.readonly_role,
            company=self.company)

    def test_both_actions_registered_in_catalogue(self):
        keys = {a.key for a in all_actions()}
        self.assertIn(AJUSTER_STOCK.key, keys)
        self.assertIn(BROUILLON_COMMANDE_FOURNISSEUR.key, keys)

    def test_permitted_user_sees_both_actions(self):
        keys = {a.key for a in for_user(self.magasinier)}
        self.assertIn(AJUSTER_STOCK.key, keys)
        self.assertIn(BROUILLON_COMMANDE_FOURNISSEUR.key, keys)

    def test_readonly_user_sees_neither_action(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertNotIn(AJUSTER_STOCK.key, keys)
        self.assertNotIn(BROUILLON_COMMANDE_FOURNISSEUR.key, keys)

    def test_actions_required_permissions(self):
        self.assertEqual(AJUSTER_STOCK.required_permission, 'stock_mouvement')
        self.assertEqual(
            BROUILLON_COMMANDE_FOURNISSEUR.required_permission, 'stock_creer')

    def test_inputs_never_include_company(self):
        for action in (AJUSTER_STOCK, BROUILLON_COMMANDE_FOURNISSEUR):
            props = action.inputs.get('properties', {})
            self.assertNotIn('company', props, action.key)

    def test_catalogue_endpoint_lists_actions_for_permitted_user(self):
        api = auth(self.magasinier)
        resp = api.get('/api/django/agent/actions/')
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        self.assertIn(AJUSTER_STOCK.key, keys)
        self.assertIn(BROUILLON_COMMANDE_FOURNISSEUR.key, keys)


class StockAgentActionRelayedCallTest(TestCase):
    """Un mouvement POSTé via l'endpoint relayé force la société serveur."""

    def setUp(self):
        register_stock_actions()
        self.company = Company.objects.create(nom='AG7 Relay Co', slug='ag7-relay')
        self.other = Company.objects.create(nom='AG7 Other', slug='ag7-other')
        self.role = Role.objects.create(
            company=self.company, nom='Magasinier',
            permissions=['stock_voir', 'stock_mouvement'])
        self.user = User.objects.create_user(
            username='ag7_relay', password='x', role=self.role,
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AG7', quantite_stock=0,
            prix_vente=100)

    def test_movement_posts_through_endpoint_with_company_forced(self):
        api = auth(self.user)
        resp = api.post(AJUSTER_STOCK.endpoint, {
            'produit': self.produit.id,
            'type_mouvement': MouvementStock.TypeMouvement.ENTREE,
            'quantite': 5,
            # Tentative d'injection : la société est ignorée côté serveur.
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        mv = MouvementStock.objects.get(produit=self.produit)
        # Société forcée à celle du caller (jamais celle envoyée dans le corps).
        self.assertEqual(mv.company_id, self.company.id)
        self.assertEqual(mv.quantite, 5)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)
