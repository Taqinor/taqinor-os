"""NTPLT61 — logique PURE d'import de tenant (tri topologique + plan de remap).

Sans base : on teste ``_toposort`` / ``build_import_plan`` et ``read_export``
(zip en mémoire). L'application en base (``apply_import``) est couverte par le
gate combiné de l'orchestrateur ; ici on verrouille la logique d'ordonnancement
qui garantit qu'une FK n'est jamais résolue avant sa cible."""
import io
import json
import zipfile

from django.test import SimpleTestCase

from core import tenant_import


class ToposortTests(SimpleTestCase):
    def test_dependency_before_dependent(self):
        # devis dépend de client ; client doit venir AVANT devis.
        labels = ['ventes.devis', 'crm.client']
        deps = {'ventes.devis': {'crm.client'}, 'crm.client': set()}
        order = tenant_import._toposort(labels, deps)
        self.assertLess(order.index('crm.client'), order.index('ventes.devis'))

    def test_chain_ordering(self):
        labels = ['c', 'b', 'a']
        deps = {'c': {'b'}, 'b': {'a'}, 'a': set()}
        self.assertEqual(tenant_import._toposort(labels, deps), ['a', 'b', 'c'])

    def test_cycle_and_selfref_do_not_hang(self):
        labels = ['x', 'y', 'z']
        # x<->y cycle, z self-ref ; ne doit pas boucler à l'infini.
        deps = {'x': {'y'}, 'y': {'x'}, 'z': {'z'}}
        order = tenant_import._toposort(labels, deps)
        self.assertCountEqual(order, labels)

    def test_edge_to_absent_label_ignored(self):
        labels = ['a']
        deps = {'a': {'missing'}}
        self.assertEqual(tenant_import._toposort(labels, deps), ['a'])


class BuildImportPlanTests(SimpleTestCase):
    def test_plan_orders_by_fk(self):
        records = [
            {'model': 'ventes.devis', 'pk': 1, 'fields': {}},
            {'model': 'crm.client', 'pk': 5, 'fields': {}},
        ]
        fk_map = {'ventes.devis': {'client_id': 'crm.client'}}
        order, deps = tenant_import.build_import_plan(records, fk_map)
        self.assertLess(order.index('crm.client'), order.index('ventes.devis'))
        self.assertEqual(deps['ventes.devis'], {'crm.client'})


class ReadExportTests(SimpleTestCase):
    def _zip(self, files):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        buf.seek(0)
        return buf

    def test_reads_valid_export(self):
        buf = self._zip({
            'manifest.json': json.dumps({'format': 'taqinor-tenant-export/1'}),
            'minio-manifest.json': json.dumps([{'key': 'a'}]),
            'data/crm.client.json': json.dumps(
                [{'model': 'crm.client', 'pk': 1, 'fields': {'nom': 'X'}}]),
        })
        manifest, records, minio = tenant_import.read_export(buf)
        self.assertEqual(manifest['format'], 'taqinor-tenant-export/1')
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['model'], 'crm.client')
        self.assertEqual(len(minio), 1)

    def test_rejects_unknown_format(self):
        buf = self._zip({'manifest.json': json.dumps({'format': 'bogus/9'})})
        with self.assertRaises(tenant_import.TenantImportError):
            tenant_import.read_export(buf)

    def test_rejects_missing_manifest(self):
        buf = self._zip({'data/x.json': '[]'})
        with self.assertRaises(tenant_import.TenantImportError):
            tenant_import.read_export(buf)
