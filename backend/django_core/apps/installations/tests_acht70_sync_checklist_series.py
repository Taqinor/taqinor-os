"""ACHT70 (C-ACHT-067) — l'op de synchro `chantier.cocher_checklist` accepte
`equipements` (forme du contrat ACHT40) et crée les équipements par le même
service que l'action en ligne ; le rejeu ne duplique rien ; sans `equipements`
l'op coche seulement.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht70_sync_checklist_series"
"""
import copy
import json
from pathlib import Path

from apps.installations.services import ensure_checklist_items
from apps.installations.tests_field_sync import (
    SYNC_URL, FieldSyncBaseTest, make_produit,
)
from apps.sav.models import Equipement

ECHANTILLON = (Path(__file__).resolve().parent / 'contract_samples'
               / 'field_sync_cocher_checklist.json')


class SyncChecklistSeriesTests(FieldSyncBaseTest):
    def setUp(self):
        super().setUp()
        self.panneau = make_produit(self.company, nom='Panneau ACHT70')
        self.cle = ensure_checklist_items(self.inst)[0].cle

    def _corps(self, equipements):
        # Corps tiré de l'échantillon partagé (ACHT40), ids réels substitués.
        corps = copy.deepcopy(json.loads(
            ECHANTILLON.read_text(encoding='utf-8'))['requete'])
        op = corps['ops'][0]
        op['client_op_id'] = 'acht70-op-1'
        op['payload'].update({
            'chantier': self.inst.id, 'cle': self.cle, 'fait': True,
            'equipements': equipements})
        return {'ops': [op]}

    def _parc(self, serie):
        return Equipement.objects.filter(
            company=self.company, numero_serie=serie).count()

    def test_serie_hors_ligne_arrive_au_parc(self):
        r = self.api.post(SYNC_URL, self._corps(
            [{'produit': self.panneau.id, 'numero_serie': 'SN-OFF-1'}]),
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['errors'], 0, r.data)
        self.assertTrue(self.inst.checklist.get(cle=self.cle).fait)
        self.assertEqual(self._parc('SN-OFF-1'), 1)

    def test_rejeu_sans_doublon(self):
        corps = self._corps(
            [{'produit': self.panneau.id, 'numero_serie': 'SN-OFF-1'}])
        self.api.post(SYNC_URL, corps, format='json')
        r = self.api.post(SYNC_URL, corps, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._parc('SN-OFF-1'), 1)
        # Une nouvelle op (autre client_op_id) avec la même série : doublon
        # signalé par le service, jamais un second équipement ni un 500.
        corps['ops'][0]['client_op_id'] = 'acht70-op-2'
        r = self.api.post(SYNC_URL, corps, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._parc('SN-OFF-1'), 1)

    def test_sans_equipements_coche_seulement(self):
        r = self.api.post(SYNC_URL, self._corps([]), format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(self.inst.checklist.get(cle=self.cle).fait)
        self.assertEqual(Equipement.objects.filter(
            company=self.company, installation=self.inst).count(), 0)
