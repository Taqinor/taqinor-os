"""CIQ123 — prix de vente par palier de quantité (saisi) et disponibilité
« sur commande ». Contrat partagé : ``contract_samples/produit_ci.json``
(``champs_produit.paliers_prix_vente``).
"""
import json
from decimal import Decimal
from importlib import import_module
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.ventes.moteur_ci.composition import composer_ci
from authentication.models import Company

User = get_user_model()
URL = '/api/django/stock/produits/'
CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_ci.json')
    .read_text(encoding='utf-8'))
PALIERS = [{'seuil_min': 0, 'seuil_max': 100, 'prix_vente_ttc': '1400'},
           {'seuil_min': 100, 'seuil_max': None, 'prix_vente_ttc': '1300'}]


def _cles(objet):
    if isinstance(objet, dict):
        for k, v in objet.items():
            yield k
            yield from _cles(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from _cles(v)


class CompositionPaliersTests(SimpleTestCase):
    def _composer(self, module):
        return composer_ci(
            705 * 0.71, [], onduleurs={'combinaison': []},
            entrees={'module': module, 'tension': 'BT',
                     'type_pose': 'bac_acier'}, forfaits={})

    def test_705_panneaux_au_prix_du_palier(self):
        comp = self._composer({'produit': 1, 'designation': 'Panneau 710 W',
                               'pmax_wc': 710, 'prix_connu': True,
                               'paliers_prix_vente': PALIERS,
                               'delai_appro_jours': 45})
        panneaux = comp['lignes'][0]
        self.assertEqual(panneaux['quantite'], 705)
        self.assertEqual(Decimal(panneaux['prix_unitaire_ttc']),
                         Decimal('1300.00'))
        self.assertEqual(panneaux['palier']['seuil_min'], 100)
        self.assertEqual(panneaux['delai_appro_jours'], 45)

    def test_paliers_vides_prix_inchange(self):
        comp = self._composer({'produit': 1, 'designation': 'Panneau 710 W',
                               'pmax_wc': 710, 'prix_connu': True,
                               'paliers_prix_vente': []})
        panneaux = comp['lignes'][0]
        self.assertNotIn('prix_unitaire_ttc', panneaux)
        self.assertNotIn('palier', panneaux)

    def test_aucune_cle_prix_achat(self):
        comp = self._composer({'produit': 1, 'designation': 'P',
                               'pmax_wc': 710, 'prix_connu': True,
                               'paliers_prix_vente': PALIERS})
        self.assertNotIn('prix_achat', set(_cles(comp)))

    def test_migration_additive_reversible(self):
        module = import_module(
            'apps.stock.migrations.0165_ciq123_paliers_vente')
        ops = module.Migration.operations
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], migrations.AddField)
        self.assertTrue(ops[0].reversible)
        self.assertEqual(ops[0].name, 'paliers_prix_vente')

    def test_cle_du_contrat(self):
        self.assertIn('paliers_prix_vente', CONTRAT['champs_produit'])


class PaliersApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.get_or_create(
            slug='ciq123-co', defaults={'nom': 'CIQ123 Co'})[0]
        roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            roles[nom] = Role.objects.create(
                company=company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='ciq123_dir', password='x', company=company,
            role=roles['Directeur'])

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_saisie_et_relecture(self):
        r = self._api().post(URL, {'nom': 'Panneau 710 W', 'prix_vente': '1272',
                                   'paliers_prix_vente': PALIERS},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['paliers_prix_vente'][1]['prix_vente_ttc'],
                         '1300')
        self.assertIsNone(r.data['paliers_prix_vente'][1]['seuil_max'])

    def test_vide_par_defaut(self):
        r = self._api().post(URL, {'nom': 'Article', 'prix_vente': '1'},
                             format='json')
        self.assertEqual(r.data['paliers_prix_vente'], [])

    def test_recouvrement_refuse(self):
        r = self._api().post(URL, {'nom': 'X', 'prix_vente': '1',
                                   'paliers_prix_vente': [
                                       {'seuil_min': 0, 'seuil_max': 150,
                                        'prix_vente_ttc': '10'},
                                       {'seuil_min': 100, 'seuil_max': None,
                                        'prix_vente_ttc': '9'}]},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('paliers_prix_vente', r.data)
