# -*- coding: utf-8 -*-
"""ACAL169 — « peut-on publier ? » : UNE réponse, celle de verdict_publiable.

Avant : ``evaluation_electrique['publiable']`` et
``verdict_publiable['publiable']`` étaient deux définitions ; l'affectation
imposée, le polystring et les micro-onduleurs n'entraient que dans la
première — l'écran affichait « Publiable » sur une chaîne trop longue.
Base RÉELLE (Produit / FicheTechnique / réglages), aucun patch.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, CODE_AFFECTATION, CODE_FICHE_INCOMPLETE,
    CODE_MICRO_ONDULEURS, CODE_POLYSTRING, evaluation_electrique,
    verdict_publiable,
)
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{'id': 'a', 'label': 'PAN-A', 'result': {'count': 24},
               'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0}],
}
REFUSANTS = ('bloquant', 'sans_source')


class VerdictUnique(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        self.module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=120.0, ond_mppt_v_max=500.0, ond_v_max_abs=600.0,
            ond_i_max_mppt_a=26.0, ond_ac_kw=10.0, ond_phases=3)
        self.base = {
            'module_produit': self.module.pk,
            'onduleur_produit': self.onduleur.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
            'phases': 3, 'regime': 'TT',
            # La justification de terre RÉELLE (CAL134).
            'terre': {'justification_continuite': True},
        }

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL169-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _calepinage(self, **entree):
        donnees = dict(self.base)
        donnees.update(entree)
        donnees = {cle: valeur for cle, valeur in donnees.items()
                   if valeur is not None}
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            roof_layout=LAYOUT, resultat={CLE_ENTREE: donnees})

    def _motifs(self, verdict, code):
        return [motif for motif in verdict['motifs']
                if motif['code'] == code]

    def test_affectation_bloquante_visible_des_deux_cotes(self):
        # ACAL265 — la clé de module est '<zone.id>#<n>' (zone 'a'), le
        # libellé « PAN-A » n'est plus une clé.
        imposee = [{'module': 'a#%d' % rang, 'chaine': 2, 'mppt': 1,
                    'onduleur': 1} for rang in range(1, 21)]
        calepinage = self._calepinage(affectation_manuelle=imposee)
        verdict = verdict_publiable(calepinage)
        motifs = self._motifs(verdict, CODE_AFFECTATION)
        self.assertTrue(motifs, verdict['motifs'])
        self.assertTrue(motifs[0]['libelle'].startswith(
            'Chaîne 2 (pan a) : 20 modules, maximum'), motifs[0])
        self.assertIn(motifs[0]['statut'], REFUSANTS)
        self.assertFalse(verdict['publiable'])
        self.assertFalse(evaluation_electrique(calepinage)['publiable'])

    def test_polystring_bloquant(self):
        calepinage = self._calepinage(
            polystring=[{'mppt': 99, 'pans': ['PAN-A']}])
        verdict = verdict_publiable(calepinage)
        self.assertTrue(self._motifs(verdict, CODE_POLYSTRING),
                        verdict['motifs'])
        self.assertFalse(verdict['publiable'])
        self.assertFalse(evaluation_electrique(calepinage)['publiable'])

    def test_micro_bloquant(self):
        micro = self._produit(nom='Micro sans borne', type_fiche='optimiseur',
                              opt_ac_kw=0.8, opt_ac_tension_v=230.0)
        calepinage = self._calepinage(onduleur_produit=None,
                                      optimiseur_produit=micro.pk)
        verdict = verdict_publiable(calepinage)
        motifs = self._motifs(verdict, CODE_MICRO_ONDULEURS)
        self.assertTrue([motif for motif in motifs
                         if motif['statut'] in REFUSANTS], verdict['motifs'])
        self.assertFalse(verdict['publiable'])
        self.assertFalse(evaluation_electrique(calepinage)['publiable'])

    def test_indetermine_distinct_du_bloquant(self):
        calepinage = self._calepinage(module_produit=None,
                                      onduleur_produit=None)
        verdict = verdict_publiable(calepinage)
        manques = self._motifs(verdict, CODE_FICHE_INCOMPLETE)
        self.assertTrue(manques, verdict['motifs'])
        for motif in manques:
            self.assertNotIn(motif['statut'], REFUSANTS)
        self.assertEqual(evaluation_electrique(calepinage)['verdict'],
                         'indetermine')

    def test_publiable_derive_de_verdict_publiable(self):
        for entree in ({}, {'affectation_manuelle': [
                {'module': 'PAN-A#%d' % rang, 'chaine': 2, 'mppt': 1,
                 'onduleur': 1} for rang in range(1, 21)]}):
            with self.subTest(entree=bool(entree)):
                calepinage = self._calepinage(**entree)
                self.assertEqual(
                    evaluation_electrique(calepinage)['publiable'],
                    verdict_publiable(calepinage)['publiable'])
