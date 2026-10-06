"""ACAL36 (C-ACAL-115/114) — le contexte de conception du calepinage sert
``revision_possible`` et le devis lié (référence, statut, client) selon le
contrat ``calepinage_design_context.json``.

``revision_possible`` est LU sur ventes (``devis_modifiabilite`` →
``domain.modifiabilite.verdict``, réel) ; ``calepinage.devis_lie`` reprend le
bloc ``devis`` du contexte ventes. Aucun mock : APIClient réel, base réelle.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_design_context.json').read_text(encoding='utf-8'))

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class ContexteDevisLieTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Client ACAL36')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Lead ACAL36')

    def _calepinage_lie(self, statut):
        devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference=f'DEV-ACAL36-{statut}', statut=statut)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=devis,
            titre=f'QA-ACAL36-{statut}', roof_layout=LAYOUT)
        return calepinage, devis

    def _contexte(self, calepinage):
        reponse = self.api.get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_accepte_revision_possible_et_devis_lie(self):
        attendu = CONTRAT['exemple_accepte']
        calepinage, devis = self._calepinage_lie(Devis.Statut.ACCEPTE)
        contexte = self._contexte(calepinage)
        self.assertIs(contexte['revision_possible'], True)
        self.assertEqual(attendu['revision_possible'], True)
        devis_lie = contexte['calepinage']['devis_lie']
        self.assertEqual(sorted(devis_lie),
                         sorted(attendu['calepinage']['devis_lie']))
        self.assertEqual(devis_lie['id'], devis.pk)
        self.assertEqual(devis_lie['reference'], devis.reference)
        self.assertEqual(devis_lie['statut'], 'accepte')
        self.assertTrue(devis_lie['client_nom'])

    def test_brouillon_revision_impossible(self):
        calepinage, _devis = self._calepinage_lie(Devis.Statut.BROUILLON)
        contexte = self._contexte(calepinage)
        self.assertIs(contexte['revision_possible'],
                      CONTRAT['exemple']['revision_possible'])
        self.assertEqual(contexte['calepinage']['devis_lie']['statut'],
                         'brouillon')

    def test_sans_devis_cles_presentes_a_null(self):
        attendu = CONTRAT['exemple_sans_devis']
        nu = Calepinage.objects.create(company=self.company,
                                       client=self.client_lie,
                                       titre='QA-ACAL36-nu')
        contexte = self._contexte(nu)
        self.assertIn('revision_possible', contexte)
        self.assertIs(contexte['revision_possible'],
                      attendu['revision_possible'])
        self.assertIn('devis_lie', contexte['calepinage'])
        self.assertIsNone(contexte['calepinage']['devis_lie'])
        # Les sept clés historiques restent toutes présentes.
        for cle in ('calepinage', 'geometrie', 'cible', 'carte', 'modifiable',
                    'raison_lecture_seule', 'avertissements'):
            self.assertIn(cle, contexte)
