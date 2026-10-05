# -*- coding: utf-8 -*-
"""ACAL160 — l'édition du schéma unifilaire FUSIONNÉE clé par clé.

Avant : un POST remplaçait TOUTE l'édition — une rubrique postée effaçait les
autres, et le libellé d'un organe momentanément non dessiné disparaissait.
Désormais : fusion par clef, ``null`` efface, une clef non dessinée postée
avec une valeur reste refusée en la nommant.
"""
from __future__ import annotations

import dataclasses
import unittest

from apps.calepinage.services.sld import (
    CLE_EDITION, SldRefuse, edition_sld, enregistrer_edition_sld,
    rendu_du_schema,
)
from core.electrique import concevoir
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

MODULE = SpecModule(vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0, designation='CS7N-710')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=500.0,
                        v_max_abs=600.0, i_max_mppt_a=26.0, ac_kw=5.0,
                        phases=1, designation='Onduleur 5 kW')


class _Calepinage:
    def __init__(self, resultat=None):
        self.pk = None
        self.resultat = resultat


def _entree():
    return EntreeElectrique(module=MODULE, onduleur=ONDULEUR,
                            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
                            dc_m=30.0, ac_m=12.0)


def _dessin(sans_parafoudre_ac=False):
    entree = _entree()
    resultat = concevoir(entree)
    if sans_parafoudre_ac:
        resultat = dataclasses.replace(resultat, protections=tuple(
            p for p in resultat.protections if p.repere != 'PAC1'))
    return rendu_du_schema(entree, resultat)


class Fusion(unittest.TestCase):

    def setUp(self):
        self.calepinage = _Calepinage(resultat={CLE_EDITION: {
            'libelles': {'parafoudre_ac': 'PF1'}, 'reperes': {},
            'positions': {}}})
        # Le parafoudre AC n'est momentanément PAS dessiné.
        self.dessin = _dessin(sans_parafoudre_ac=True)

    def _poser(self, corps):
        return enregistrer_edition_sld(self.calepinage, corps,
                                       dessin=self.dessin)

    def test_rubrique_postee_ne_perd_pas_les_autres(self):
        self._poser({'reperes': {'onduleur': 'INV1'}})
        self._poser({'libelles': {'onduleur': 'INV'}})
        edition = edition_sld(self.calepinage)
        self.assertEqual(edition['reperes'], {'onduleur': 'INV1'})
        self.assertEqual(edition['libelles'],
                         {'parafoudre_ac': 'PF1', 'onduleur': 'INV'})

    def test_cle_non_dessinee_conservee(self):
        self._poser({'libelles': {'onduleur': 'INV'}})
        self.assertEqual(
            self.calepinage.resultat[CLE_EDITION]['libelles']
            ['parafoudre_ac'], 'PF1')
        # Le parafoudre revient : il retrouve son libellé.
        entree = _entree()
        dessin = rendu_du_schema(entree, concevoir(entree),
                                 edition=edition_sld(self.calepinage))
        bloc = next(b for b in dessin['blocs']
                    if b['clef'] == 'parafoudre_ac')
        self.assertEqual(bloc['titre'], 'PF1')

    def test_null_efface_une_cle(self):
        self._poser({'libelles': {'onduleur': 'INV'}})
        self._poser({'libelles': {'onduleur': None}})
        self.assertEqual(edition_sld(self.calepinage)['libelles'],
                         {'parafoudre_ac': 'PF1'})
        self._poser({'libelles': {'parafoudre_ac': None}})
        self.assertEqual(edition_sld(self.calepinage)['libelles'], {})

    def test_cle_inconnue_refusee_nommee(self):
        avant = dict(self.calepinage.resultat[CLE_EDITION])
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'libelles': {'coffret_ac': 'Coffret AC'}})
        self.assertEqual(refus.exception.champ,
                         'edition.libelles.coffret_ac')
        self.assertEqual(self.calepinage.resultat[CLE_EDITION], avant)
