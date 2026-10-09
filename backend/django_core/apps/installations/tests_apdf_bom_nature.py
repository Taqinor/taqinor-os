"""APDF40 (C-APDF-014) — la nomenclature gelée porte `nature` par ligne.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apdf_bom_nature"
"""
import importlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.installations import services


def _ligne(produit, qte=1, designation='x'):
    return SimpleNamespace(produit=produit, quantite=qte,
                           designation=designation)


def _produit(pid, type_cat):
    return SimpleNamespace(
        id=pid, nom=f'P{pid}', marque=None,
        categorie=SimpleNamespace(type_equipement=type_cat))


class BomNatureTests(SimpleTestCase):
    def _bom(self, lignes):
        with mock.patch('apps.ventes.utils.options.option_lines',
                        return_value=lignes), \
                mock.patch.object(services, '_nombre_proprietes',
                                  return_value=1):
            return services._freeze_bom(object())

    def test_gel_nature(self):
        bom = self._bom([_ligne(_produit(1, 'panneau')),
                         _ligne(_produit(2, 'service'),
                                designation='Transport'),
                         _ligne(None)])
        self.assertEqual([x['nature'] for x in bom],
                         ['materiel', 'service', 'materiel'])

    def test_rattrapage_migration(self):
        mig = importlib.import_module(
            'apps.installations.migrations.0129_apdf40_bom_nature')
        self.assertEqual(
            mig.nature_pour_ligne({'produit_id': 2}, {2: 'service'}),
            'service')
        self.assertEqual(
            mig.nature_pour_ligne({'produit_id': 1}, {1: 'panneau'}),
            'materiel')
        self.assertEqual(
            mig.nature_pour_ligne({'produit_id': None}, {}), 'materiel')
        self.assertEqual(
            mig.nature_pour_ligne({'nature': 'service'}, {}), 'service')

    def test_quantites_stock_inchangees(self):
        bom = self._bom([_ligne(_produit(1, 'panneau'), qte=4),
                         _ligne(_produit(2, 'service'), qte=1)])
        self.assertEqual([x['quantite'] for x in bom], [4.0, 1.0])
        self.assertEqual([x['produit_id'] for x in bom], [1, 2])
