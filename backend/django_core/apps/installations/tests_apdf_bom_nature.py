"""APDF40 (C-APDF-014) — la nomenclature gelée porte `nature` par ligne.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apdf_bom_nature"
"""
import importlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

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


class BomNaturePersisteTests(TestCase):
    def test_rattrapage_migration_sur_bom_persiste(self):
        """APDF100 — `rattraper_nature` (registre historique 0129) sur un
        `Installation.bom` PERSISTÉ sans nature : nature rétro-remplie,
        quantités inchangées. Mutant : corps vidé ⇒ `bom` sans `nature`."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        from authentication.models import Company
        from apps.installations.models import Installation
        from apps.stock.models import Categorie, Produit
        co = Company.objects.create(slug='apdf100-co', nom='APDF100')
        pan, trp = (Produit.objects.create(
            company=co, nom=t, sku=f'APDF100-{t}', prix_vente=1,
            categorie=Categorie.objects.create(company=co, nom=t, type_equipement=t))
            for t in ('panneau', 'service'))
        bom = [{'produit_id': pan.id, 'quantite': 4, 'designation': 'Panneau'},
               {'produit_id': trp.id, 'quantite': 1, 'designation': 'Transport'},
               {'produit_id': None, 'quantite': 1, 'designation': 'Divers'}]
        inst = Installation.objects.create(company=co, reference='CH-APDF100', bom=bom)
        avant = services._quantites_depuis_bom(bom)
        mig = importlib.import_module(
            'apps.installations.migrations.0129_apdf40_bom_nature')
        mig.rattraper_nature(MigrationExecutor(connection).loader.project_state(
            ('installations', '0129_apdf40_bom_nature')).apps, None)
        inst.refresh_from_db()
        self.assertEqual([x['nature'] for x in inst.bom],
                         ['materiel', 'service', 'materiel'])
        self.assertEqual(services._quantites_depuis_bom(inst.bom), avant)
