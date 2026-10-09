"""ACHT31 (C-ACHT-029) — contrat PARTAGÉ des ops de synchro terrain
horodatées (`contract_samples/field_sync_ops.json`), posé seul sur main
(PACT10) ; ce test producteur le charge et exige un exemple pour CHAQUE
`op_type` du registre de `field_sync.py`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_contrat_sync"
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.installations import field_sync

CONTRAT = (Path(field_sync.__file__).parent / 'contract_samples'
           / 'field_sync_ops.json')


class ContratSyncTests(SimpleTestCase):
    def setUp(self):
        self.doc = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_contrat_charge_et_couvre_les_op_types(self):
        exemples = self.doc['exemples_ops']
        manquants = sorted(set(field_sync.FIELD_OP_HANDLERS) - set(exemples))
        self.assertEqual(
            manquants, [], f'op_type sans exemple dans le contrat : {manquants}')
        for op_type, ex in exemples.items():
            self.assertIn(op_type, field_sync.FIELD_OP_HANDLERS)
            self.assertIn('client_op_id', ex, op_type)
            self.assertIn('payload', ex, op_type)

    def test_champs_temporels_et_conflit_documentes(self):
        exemples = self.doc['exemples_ops']
        for op_type in ('intervention.checkin', 'intervention.depart_depot',
                        'intervention.retour', 'intervention.signer_client',
                        'intervention.consommation_ligne'):
            self.assertIn('client_ts', exemples[op_type], op_type)
        self.assertIn('base_updated_at',
                      exemples['intervention.consommation_ligne'])
        statuts = {r['status'] for r in self.doc['exemple']['results']}
        self.assertIn('conflit', statuts)
        conflit = next(r for r in self.doc['exemple']['results']
                       if r['status'] == 'conflit')
        self.assertIn('detail', conflit)
        self.assertIn('valeur_serveur', conflit)
        self.assertEqual(self.doc['endpoint'],
                         'POST /api/django/installations/sync/')
