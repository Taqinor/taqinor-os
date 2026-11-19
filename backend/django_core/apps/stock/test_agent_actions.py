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
        # Magasinier : stock_mouvement + stock_creer, PAS achats_commander
        # (REP2 : la garde réelle de la création d'un BCF).
        self.magasinier_role = Role.objects.create(
            company=self.company, nom='Magasinier',
            permissions=['stock_voir', 'stock_creer', 'stock_mouvement'])
        self.magasinier = User.objects.create_user(
            username='ag7_mag', password='x', role=self.magasinier_role,
            company=self.company)
        # Acheteur : porte achats_commander (Directeur / Administrateur).
        self.acheteur = User.objects.create_user(
            username='ag7_ach', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Acheteur',
                                     permissions=['stock_voir', 'achats_commander']))
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
        # REP2 — stock_creer sans achats_commander : la route refuserait (403).
        self.assertNotIn(BROUILLON_COMMANDE_FOURNISSEUR.key, keys)
        self.assertIn(BROUILLON_COMMANDE_FOURNISSEUR.key,
                      {a.key for a in for_user(self.acheteur)})

    def test_readonly_user_sees_neither_action(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertNotIn(AJUSTER_STOCK.key, keys)
        self.assertNotIn(BROUILLON_COMMANDE_FOURNISSEUR.key, keys)

    def test_actions_required_permissions(self):
        self.assertEqual(AJUSTER_STOCK.required_permission, 'stock_mouvement')
        self.assertEqual(
            BROUILLON_COMMANDE_FOURNISSEUR.required_permission,
            'achats_commander')

    def test_mouvement_entree_sortie_seulement_et_a_confirmer(self):
        """REP1 — « ajustement » fixe le stock À la quantité (niveau visé,
        ``perform_create``) : il n'est plus offert ; les deux sens offerts
        sont des valeurs EXACTES du modèle ; quantité entière ≥ 1 ; une
        quantité de stock change → proposition à confirmer."""
        from core.champs_stricts import QUANTITE_MAX
        from apps.agent.registry import RISK_OUTWARD
        props = AJUSTER_STOCK.inputs['properties']
        sens = props['type_mouvement']['enum']
        self.assertEqual(sens, ['entree', 'sortie'])
        self.assertLessEqual(set(sens), set(MouvementStock.TypeMouvement.values))
        self.assertNotIn('ajustement', str(AJUSTER_STOCK.inputs).lower())
        self.assertEqual((props['quantite']['type'], props['quantite']['minimum'],
                          props['quantite']['maximum']),
                         ('integer', 1, QUANTITE_MAX))
        self.assertEqual(AJUSTER_STOCK.risk, RISK_OUTWARD)
        self.assertIn('AJOUTE', AJUSTER_STOCK.confirm_summary)
        self.assertIn('RETIRE', AJUSTER_STOCK.confirm_summary)
        # Avec un objet nommé, le relais n'affiche que le LABEL en 1re ligne
        # de l'aperçu (confirm_summary écarté) : le label dit le sens.
        self.assertIn('entrée AJOUTE, une sortie RETIRE', AJUSTER_STOCK.label)
        self.assertIn("rien n'est envoyé", BROUILLON_COMMANDE_FOURNISSEUR.label)
        for action in (AJUSTER_STOCK, BROUILLON_COMMANDE_FOURNISSEUR):
            self.assertTrue(action.objets)
            self.assertLessEqual(len(action.label), 90, action.key)
        desc = AJUSTER_STOCK.description
        self.assertLessEqual(len(desc), 600)
        for section in ('Sert à :', 'Ne pas utiliser pour :', 'Exemple :',
                        'Résultat :'):
            self.assertIn(section, desc)

    def test_permission_du_catalogue_est_la_garde_de_la_route(self):
        """REP1/REP2 — le code du catalogue est un code que la route EXIGE
        (gardes lues sur la vue, comme le test de parité de l'agent)."""
        from apps.agent.tests.test_registry import _gardes_de_la_route
        for action in (AJUSTER_STOCK, BROUILLON_COMMANDE_FOURNISSEUR):
            codes, _admin, _modules = _gardes_de_la_route(action)
            self.assertIn(action.required_permission, codes, action.key)

    def test_bcf_brouillon_a_confirmer_et_lignes_sans_prix(self):
        """REP2 — un BCF engage la société même en brouillon : proposition à
        confirmer qui dit « rien n'est envoyé » ; une ligne n'accepte que
        produit / désignation / quantité entière, jamais un prix."""
        from apps.agent.registry import RISK_OUTWARD
        self.assertEqual(BROUILLON_COMMANDE_FOURNISSEUR.risk, RISK_OUTWARD)
        self.assertIn("rien n'est envoyé",
                      BROUILLON_COMMANDE_FOURNISSEUR.confirm_summary)
        ligne = BROUILLON_COMMANDE_FOURNISSEUR.inputs['properties']['lignes']['items']
        self.assertEqual(set(ligne['properties']),
                         {'produit', 'designation', 'quantite'})
        self.assertIs(ligne['additionalProperties'], False)
        self.assertEqual(ligne['properties']['quantite']['type'], 'integer')
        self.assertNotIn('prix', str(BROUILLON_COMMANDE_FOURNISSEUR.inputs))
        self.assertLessEqual(len(BROUILLON_COMMANDE_FOURNISSEUR.description), 600)

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
        resp = auth(self.acheteur).get('/api/django/agent/actions/')
        self.assertIn(BROUILLON_COMMANDE_FOURNISSEUR.key,
                      {a['key'] for a in resp.data['actions']})


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

    def test_sortie_retire_la_quantite_du_stock(self):
        """REP1 — une sortie relayée RETIRE la quantité (5 → 2), elle ne fixe
        jamais le stock à la valeur envoyée."""
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=5)
        resp = auth(self.user).post(AJUSTER_STOCK.endpoint, {
            'produit': self.produit.id, 'type_mouvement': 'sortie',
            'quantite': 3}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 2)


class StockLibellesAssistantTest(TestCase):
    """Copilote vague 2 — l'aperçu d'une proposition NOMME le produit, le
    fournisseur et le bon de commande (``selectors_libelles.libelles_stock``
    via la table de l'agent) : jamais un prix ni un montant ; un rôle sans
    code du module Stock, ou d'une autre société, ne reçoit rien."""

    def test_objets_declares_et_nommes_sans_prix(self):
        from apps.agent.libelles import libelles_objets
        from apps.stock.models import BonCommandeFournisseur, Fournisseur
        self.assertEqual(AJUSTER_STOCK.objets, {'produit': 'produit'})
        self.assertEqual(BROUILLON_COMMANDE_FOURNISSEUR.objets, {'fournisseur': 'fournisseur'})
        company = Company.objects.create(nom='AG7 Lib', slug='ag7-lib')
        produit = Produit.objects.create(company=company, nom='Panneau 550', sku='PAN-550',
                                         prix_vente=1234, prix_achat=987)
        fournisseur = Fournisseur.objects.create(company=company, nom='Atlas Solaire')
        bcf = BonCommandeFournisseur.objects.create(
            company=company, reference='BCF-LIB-1', fournisseur=fournisseur)
        ids = {'produit': produit.pk, 'fournisseur': fournisseur.pk, 'bcf': bcf.pk}

        def libelles(permissions, societe=company):
            user = User.objects.create_user(
                username=f'ag7_lib_{len(permissions)}_{societe.pk}', password='x', company=societe,
                role=Role.objects.create(company=societe, nom=f'L{len(permissions)}',
                                         permissions=permissions))
            return libelles_objets(user, ids)
        out = libelles(['stock_voir'])
        self.assertEqual(out, {'produit': 'Panneau 550 — PAN-550', 'fournisseur': 'Atlas Solaire',
                               'bcf': 'BCF-LIB-1 — Atlas Solaire (brouillon)'})
        self.assertNotIn('1234', str(out))
        self.assertNotIn('987', str(out))
        self.assertEqual(libelles(['crm_voir', 'crm_creer']), {})
        autre = Company.objects.create(nom='AG7 Lib 2', slug='ag7-lib-2')
        self.assertEqual(libelles(['stock_voir'], autre), {})
