# -*- coding: utf-8 -*-
"""ACAL162 — un calepinage 100 % micro-onduleurs, sans onduleur de chaîne.

Avant : sans onduleur de chaîne désigné, la conception se déclarait
« fiche incomplète » (six champs « onduleur : … » manquants) et le bloc des
micro-onduleurs n'était jamais calculé. Désormais : branches AC + départs
QAC.N publiés, verdicts de chaîne OMIS en le disant, aucun onduleur fictif.
Produit / FicheTechnique RÉELS en base, aucune fiche doublée.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.chaines import MOTIF_MICRO_SEUL
from apps.calepinage.services.electrique import CLE_ENTREE
from apps.calepinage.services.sld import MOTIF_SCHEMA_MICRO_SEUL
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'z%d' % rang, 'label': 'PAN-%d' % rang,
         'result': {'count': 6},
         'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0}
        for rang in (1, 2, 3)
    ],
}

CODES_DE_CHAINE = ('voc_cold_under_vmax', 'vmp_cold_under_mppt_max',
                   'vmp_hot_over_mppt_min', 'courant_par_entree_mppt',
                   'ratio_dc_ac')


def _url(pk, suffixe):
    return f'{url_detail(pk)}{suffixe}/'


class MicroSeul(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        self.module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.micro = self._produit(
            nom='Micro 800', type_fiche='optimiseur', opt_ac_kw=0.8,
            opt_ac_tension_v=230.0, opt_ac_i_max_a=3.5,
            opt_ac_unites_max_par_branche=7)
        self.onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)
        self.entree = {
            'module_produit': self.module.pk,
            'optimiseur_produit': self.micro.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
        }
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, resultat={CLE_ENTREE: dict(self.entree)})

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL162-{nom}',
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

    def test_bloc_micro_applique_sans_onduleur_de_chaine(self):
        resultat = self._resultat()
        micro = resultat['electrique']['micro_onduleurs']
        self.assertTrue(micro['applique'])
        self.assertEqual(micro['unites'], 18)
        self.assertEqual(len(micro['branches']), 3)
        reperes = [organe['repere'] for organe in resultat['protections']]
        self.assertIn('QAC.1', reperes)
        # Les W2.N sont publiés, ou leur omission NOMME la longueur.
        textes = ' '.join(resultat['avertissements'])
        self.assertTrue(micro.get('cables') or 'longueur_m' in textes)
        self.assertFalse([texte for texte in resultat['avertissements']
                          if texte.startswith('onduleur : ')])

    def test_verdicts_de_chaine_omis_et_dits(self):
        evaluation = self.api.post(
            _url(self.calepinage.pk, 'evaluer-electrique'), {},
            format='json')
        self.assertEqual(evaluation.status_code, 200, evaluation.data)
        self.assertEqual(evaluation.data['manquantes'], [])
        self.assertNotEqual(evaluation.data['verdict'], 'indetermine')
        verdicts = {verdict['code']: verdict
                    for verdict in self._resultat()['electrique']['verdicts']}
        for code in CODES_DE_CHAINE:
            self.assertIsNone(verdicts[code]['conforme'], code)
            self.assertEqual(verdicts[code]['detail'], MOTIF_MICRO_SEUL)

    def test_avec_onduleur_de_chaine_inchange(self):
        entree = dict(self.entree, onduleur_produit=self.onduleur.pk)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            resultat={CLE_ENTREE: entree})
        resultat = self._resultat()
        verdicts = {verdict['code']: verdict
                    for verdict in resultat['electrique']['verdicts']}
        self.assertNotEqual(verdicts['voc_cold_under_vmax']['detail'],
                            MOTIF_MICRO_SEUL)
        self.assertTrue(resultat['electrique']['affectation'])

    def test_schema_micro(self):
        reponse = self.api.get(_url(self.calepinage.pk, 'schema-unifilaire'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['manquantes'], [])
        self.assertIsNone(reponse.data['svg'])
        self.assertEqual(reponse.data['bloquants'],
                         [MOTIF_SCHEMA_MICRO_SEUL])
