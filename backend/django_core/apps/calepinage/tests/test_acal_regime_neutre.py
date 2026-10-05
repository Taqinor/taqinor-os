# -*- coding: utf-8 -*-
"""ACAL152 — plus de « TT par défaut » côté calepinage.

Sans régime de neutre SAISI : aucun différentiel DDR1 posé, l'omission est
nommée (check-list, verdict publiable), le cartouche du schéma imprime
« Régime non précisé ». Saisi : la protection et le cartouche le suivent.
Base RÉELLE (Produit / FicheTechnique / réglages société), aucune source
mockée.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, CODE_REGIME_NON_PRECISE, verdict_publiable,
)
from apps.stock.models import FicheTechnique, Produit
from core.electrique.protections import MOTIF_REGIME_NON_PRECISE

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{
        'id': 'z1', 'label': 'Sud', 'neededPanels': 12,
        'result': {'count': 12},
        'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
    }],
}


def _url(pk, suffixe):
    return f'{url_detail(pk)}{suffixe}/'


class Regime(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)
        self.entree = {
            'module_produit': module.pk, 'onduleur_produit': onduleur.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
            'phases': 3,
        }
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, resultat={CLE_ENTREE: dict(self.entree)})

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL152-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _reperes(self):
        reponse = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return ([organe['repere'] for organe in reponse.data['protections']],
                reponse.data['avertissements'])

    def _svg(self):
        reponse = self.api.get(_url(self.calepinage.pk, 'schema-unifilaire'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['svg'])
        return reponse.data['svg']

    def test_sans_saisie_pas_de_ddr1_et_omission_nommee(self):
        reperes, avertissements = self._reperes()
        self.assertTrue(reperes)
        self.assertNotIn('DDR1', reperes)
        self.assertIn(MOTIF_REGIME_NON_PRECISE, avertissements)
        self.assertIn('Régime non précisé', self._svg())
        codes = [motif['code']
                 for motif in verdict_publiable(self.calepinage)['motifs']]
        self.assertIn(CODE_REGIME_NON_PRECISE, codes)
        # Absence de saisie = clé absente : aucune valeur par défaut écrite.
        self.calepinage.refresh_from_db()
        self.assertNotIn('regime', self.calepinage.resultat[CLE_ENTREE])

    def test_tn_change_la_checklist_et_le_cartouche(self):
        poste = self.api.post(_url(self.calepinage.pk, 'entree-electrique'),
                              {'regime': 'TN'}, format='json')
        self.assertEqual(poste.status_code, 200, poste.data)
        reperes, avertissements = self._reperes()
        self.assertNotIn('DDR1', reperes)
        self.assertNotIn(MOTIF_REGIME_NON_PRECISE, avertissements)
        self.assertIn('TN · triphasé', self._svg())
        lu = self.api.get(_url(self.calepinage.pk, 'entree-electrique'))
        self.assertEqual(lu.data['entree']['regime'], 'TN')
        codes = [motif['code']
                 for motif in verdict_publiable(self.calepinage)['motifs']]
        self.assertNotIn(CODE_REGIME_NON_PRECISE, codes)

    def test_tt_pose_le_ddr1(self):
        poste = self.api.post(_url(self.calepinage.pk, 'entree-electrique'),
                              {'regime': 'TT'}, format='json')
        self.assertEqual(poste.status_code, 200, poste.data)
        reperes, _avertissements = self._reperes()
        self.assertIn('DDR1', reperes)
        self.assertIn('TT · triphasé', self._svg())

    def test_valeur_inconnue_refusee(self):
        poste = self.api.post(_url(self.calepinage.pk, 'entree-electrique'),
                              {'regime': 'ZZ'}, format='json')
        self.assertEqual(poste.status_code, 400, poste.data)
        self.assertIn('regime', poste.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE], self.entree)
