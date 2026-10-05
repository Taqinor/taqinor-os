# -*- coding: utf-8 -*-
"""ACAL164 — dimensionner à une température de CELLULE, pas à la T2m.

Le noyau documente ``temp_chaud_c`` comme la température de CELLULE maximale
(``core/electrique/types.py``) ; le calepinage y posait la T2m AMBIANTE
maximale du TMY. Désormais : T_cellule = T2m max + (NOCT − 20) × 1000 / 800
quand la fiche module publie ``noct_c`` ; sinon le repli nommé du noyau
(70 °C) ; la saisie manuelle prime toujours. Fournisseur TMY injecté (aucun
réseau), Produit module RÉEL en base.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, MENTION_NON_SOURCEE, SOURCE_SAISIE, SOURCE_TMY,
    SOURCE_TMY_NOCT, conception_du_calepinage,
    enregistrer_fournisseur_temperatures,
)
from apps.stock.models import FicheTechnique, Produit
from core.electrique.types import TEMP_CHAUD_DEFAUT_C

from .test_api_liste import BaseApiCalepinage

#: Site d'Ifrane (TMY PVGIS) — les extrêmes de l'audit.
IFRANE = {'lat': 33.5333, 'lng': -5.1}


def _tmy_ifrane(lat, lon):
    return {'temperature_min_c': -9.89, 'temperature_max_c': 33.53,
            'base': 'PVGIS-SARAH3', 'fenetre_annees': '2005-2023'}


class Cellule(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.precedent = enregistrer_fournisseur_temperatures(_tmy_ifrane)
        self.addCleanup(enregistrer_fournisseur_temperatures,
                        self.precedent)

    def _calepinage(self, *, noct=None, saisie=None):
        champs = {'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59,
                  'imp_a': 17.59, 'pmax_wc': 710.0}
        if noct is not None:
            champs['noct_c'] = noct
        produit = Produit.objects.create(
            company=self.company, nom='Module %s' % noct,
            sku='ACAL164-%s' % noct, prix_achat=Decimal('999'),
            prix_vente=Decimal('1500'), quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='module',
            **champs)
        entree = dict({'module_produit': produit.pk}, **(saisie or {}))
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Ifrane',
            roof_layout={'pin': IFRANE, 'zones': []},
            resultat={CLE_ENTREE: entree})

    def test_chaud_est_une_temperature_de_cellule(self):
        conception, _m, _d, _doc = conception_du_calepinage(
            self._calepinage(noct=45))
        temperatures = conception.temperatures
        self.assertEqual(temperatures.source, SOURCE_TMY_NOCT)
        self.assertAlmostEqual(temperatures.chaud_c, 64.78, places=2)
        self.assertEqual(temperatures.froid_c, -9.89)
        self.assertIn('NOCT', temperatures.detail)

    def test_sans_noct_repli_du_noyau_nomme(self):
        conception, _m, _d, _doc = conception_du_calepinage(
            self._calepinage())
        temperatures = conception.temperatures
        self.assertEqual(temperatures.source, SOURCE_TMY)
        self.assertEqual(temperatures.chaud_c, TEMP_CHAUD_DEFAUT_C)
        self.assertNotEqual(temperatures.chaud_c, 33.53)
        self.assertEqual(temperatures.mention, MENTION_NON_SOURCEE)

    def test_saisie_prime(self):
        saisie = {'temperature_min_c': -5.0, 'temperature_max_c': 60.0}
        conception, _m, _d, _doc = conception_du_calepinage(
            self._calepinage(noct=45, saisie=saisie))
        temperatures = conception.temperatures
        self.assertEqual(temperatures.source, SOURCE_SAISIE)
        self.assertEqual(temperatures.chaud_c, 60.0)
