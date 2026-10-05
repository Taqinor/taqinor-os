# -*- coding: utf-8 -*-
"""ACAL159 — le bordereau et le schéma lisent la check-list DÉCIDÉE.

Un organe ÉCARTÉ (PAC1, motif écrit) disparaît du bordereau
(``resultat['nomenclature']``), du tableur et du schéma ; un organe AJOUTÉ par
la société entre au bordereau, marqué « décision société », jamais avec un
prix. Base RÉELLE, décisions posées par la porte HTTP.
"""
from __future__ import annotations

import json
from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.export_tableur import table_nomenclature
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{
        'id': 'z1', 'label': 'Sud', 'neededPanels': 12,
        'result': {'count': 12},
        'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
    }],
}

DECISIONS = {
    'ecartes': [{'repere': 'PAC1', 'motif': 'déjà posé'}],
    'ajouts': [{'designation': 'Coupe-circuit', 'quantite': 1,
                'motif': 'x'}],
}


def _url(pk, suffixe):
    return f'{url_detail(pk)}{suffixe}/'


class ChecklistDecidee(BaseApiCalepinage):

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
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT)
        reponse = self.api.post(_url(self.calepinage.pk, 'entree-electrique'), {
            'module_produit': module.pk, 'onduleur_produit': onduleur.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
            'phases': 3, 'regime': 'TT', 'protections': DECISIONS,
        }, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL159-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _resultat(self):
        reponse = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_ecarte_absent_du_bordereau_et_du_schema(self):
        resultat = self._resultat()
        pac1 = next(organe for organe in resultat['protections']
                    if organe['repere'] == 'PAC1')
        self.assertFalse(pac1['retenu'])
        self.assertTrue(resultat['nomenclature'])
        self.assertFalse([ligne for ligne in resultat['nomenclature']
                          if ligne['designation'].startswith('PAC1')])
        schema = self.api.get(_url(self.calepinage.pk, 'schema-unifilaire'))
        self.assertEqual(schema.status_code, 200, schema.data)
        clefs = [bloc['clef'] for bloc in schema.data['blocs']]
        self.assertNotIn('parafoudre_ac', clefs)
        self.assertIn('disjoncteur_ac', clefs)
        # L'organe ajouté, non dessinable, est SIGNALÉ sur la planche.
        self.assertIn('Coupe-circuit', schema.data['svg'])

    def test_ajout_present_au_bordereau_sans_prix(self):
        resultat = self._resultat()
        lignes = [ligne for ligne in resultat['nomenclature']
                  if 'Coupe-circuit' in ligne['designation']]
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['quantite'], 1)
        self.assertIn('décision société — x', lignes[0]['spec'])
        texte = json.dumps(resultat['nomenclature'], ensure_ascii=False)
        self.assertNotIn('prix', texte)

    def test_export_tableur_suit_le_bordereau(self):
        _entetes, lignes = table_nomenclature(self._resultat())
        designations = [str(ligne[0]) for ligne in lignes]
        self.assertFalse([texte for texte in designations
                          if texte.startswith('PAC1')])
        self.assertTrue([texte for texte in designations
                         if 'Coupe-circuit' in texte])

    def test_rouvrir_rend_le_meme_bordereau(self):
        self.assertEqual(self._resultat()['nomenclature'],
                         self._resultat()['nomenclature'])
