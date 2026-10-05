# -*- coding: utf-8 -*-
"""ACAL151 — la clé « transformateur » ADMISE dans l'entrée électrique.

Avant : ``POST entree-electrique {transformateur: …}`` répondait 400 « Champ
d'entrée électrique inconnu » — l'étape « Transformateur » de la chaîne de
pertes (CALX174), qui lit justement cette clé, ne pouvait donc JAMAIS
s'appliquer. Et sans réponse, elle disait « aucun transformateur — rien à
renseigner » : un oubli présenté comme une réponse.

Le POST est réel (vue + service), la simulation est réelle (série météo
REJOUÉE par le client double de CALX5 — aucun contexte injecté à la main).
"""
from __future__ import annotations

import unittest

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import CLE_ENTREE
from apps.calepinage.services.etapes import transformateur
from apps.calepinage.services.simulation import simuler_calepinage

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _ClientRejoue,
)

DECLARATION = {
    'declare': True,
    'perte_a_vide_kw': {'valeur': 1.2, 'source': 'fiche',
                        'reference': 'Fiche transformateur 630 kVA'},
    'perte_en_charge_kw_nominale': {'valeur': 8.0, 'source': 'fiche',
                                    'reference': 'Fiche transformateur'},
    'puissance_nominale_kw': {'valeur': 630.0, 'source': 'saisie',
                              'reference': 'Plaque signalétique'},
}


def url_entree(pk):
    return f'{url_detail(pk)}entree-electrique/'


class Transformateur(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Usine',
            roof_layout=LAYOUT)

    def _etape(self, blocs):
        return next(etape for etape in blocs['cascade']['etapes']
                    if etape['etape'] == 'transformateur')

    def _simuler(self):
        calepinage = Calepinage.objects.get(pk=self.calepinage.pk)
        rendu = simuler_calepinage(
            calepinage, forcer=True, enregistrer=False,
            client=_ClientRejoue(), materiel=MATERIEL, reglages=REGLAGES)
        return rendu['blocs']

    def test_post_accepte_puis_etape_appliquee(self):
        reponse = self.api.post(url_entree(self.calepinage.pk),
                                {'transformateur': DECLARATION},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.resultat[CLE_ENTREE]['transformateur'],
            DECLARATION)
        lu = self.api.get(url_entree(self.calepinage.pk))
        self.assertEqual(lu.data['entree']['transformateur'], DECLARATION)

        etape = self._etape(self._simuler())
        self.assertEqual(etape['motif_omission'], '')
        self.assertGreater(etape['perte_kwh'], 0.0)

    def test_declare_false_persiste_et_se_tait(self):
        reponse = self.api.post(url_entree(self.calepinage.pk),
                                {'transformateur': {'declare': False}},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        etape = self._etape(self._simuler())
        self.assertEqual(etape['motif_omission'],
                         transformateur.MOTIF_ABSENT)

    def test_sans_reponse_l_etape_dit_non_declare(self):
        etape = self._etape(self._simuler())
        self.assertEqual(etape['motif_omission'],
                         transformateur.MOTIF_NON_DECLARE)

    def test_forme_refusee_nomme_le_champ(self):
        corps = {'transformateur': {
            'declare': True, 'perte_a_vide_kw': {'valeur': 1.2}}}
        reponse = self.api.post(url_entree(self.calepinage.pk), corps,
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('transformateur.perte_a_vide_kw.source', reponse.data)
        self.calepinage.refresh_from_db()
        self.assertNotIn(
            'transformateur',
            (self.calepinage.resultat or {}).get(CLE_ENTREE) or {})


class NonDeclare(unittest.TestCase):

    def test_non_declare_motif_distinct(self):
        _, sans_reponse = transformateur.appliquer({'points': []}, {})
        _, repondu = transformateur.appliquer(
            {'points': []},
            {'entree_electrique': {'transformateur': {'declare': False}}})
        self.assertEqual(sans_reponse['motif_omission'],
                         transformateur.MOTIF_NON_DECLARE)
        self.assertEqual(repondu['motif_omission'],
                         transformateur.MOTIF_ABSENT)
        self.assertNotEqual(sans_reponse['motif_omission'],
                            repondu['motif_omission'])
