"""CAL136 — TMY v5_3 avec base de rayonnement CHOISIE, et sa provenance.

Réponse RÉELLE enregistrée le 20/09/2026 (``fixtures_pvgis/tmy_casablanca.json``,
bloc ``_provenance``) ; le fait que ``tmy`` honore bien ``raddatabase`` a été
vérifié en direct le même jour sur les deux bases. Aucun appel réseau ici.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.pvgis_serie import (
    BASE_PAR_DEFAUT, EntreeInvalide, PvgisIndisponible,
)
from apps.calepinage.tests.test_pvgis_serie import (
    TransportEnregistre, charger, client,
)


class TmyTest(unittest.TestCase):
    """La base et la fenêtre d'années accompagnent TOUT chiffre météo."""

    def setUp(self):
        self.charge = charger('tmy_casablanca.json')

    def test_base_et_fenetre_publiees_avec_lannee_type(self):
        transport = TransportEnregistre(self.charge)
        resultat = client(transport).tmy(lat=33.5, lon=-7.6)

        self.assertEqual(resultat['base'], 'PVGIS-SARAH3')
        self.assertEqual(resultat['fenetre_annees'], '2005-2023')
        self.assertEqual(resultat['base_meteo'], 'ERA5')
        # Le TMY dit de quelle ANNÉE vient chaque mois : c'est la provenance
        # de la série, et elle est republiée telle quelle.
        self.assertEqual(len(resultat['mois_retenus']), 12)
        self.assertEqual(
            sorted(m['month'] for m in resultat['mois_retenus']),
            list(range(1, 13)))

    def test_la_base_demandee_part_dans_la_requete(self):
        transport = TransportEnregistre(self.charge)
        client(transport).tmy(lat=33.5, lon=-7.6, base='PVGIS-ERA5')
        self.assertIn('raddatabase=PVGIS-ERA5', transport.appels[0])
        self.assertIn('/api/v5_3/tmy?', transport.appels[0])

    def test_base_par_defaut_explicite_dans_la_requete(self):
        transport = TransportEnregistre(self.charge)
        client(transport).tmy(lat=33.5, lon=-7.6)
        self.assertIn(f'raddatabase={BASE_PAR_DEFAUT}', transport.appels[0])

    def test_temperatures_de_dimensionnement_sourcees_de_la_serie(self):
        transport = TransportEnregistre(self.charge)
        resultat = client(transport).tmy(lat=33.5, lon=-7.6)

        # Les extrêmes sont EXACTEMENT ceux des lignes reçues : aucune
        # température de catalogue ne s'y substitue (CAL123 les reprend).
        recues = [ligne['T2m']
                  for ligne in self.charge['outputs']['tmy_hourly']]
        self.assertEqual(resultat['temperature_min_c'], min(recues))
        self.assertEqual(resultat['temperature_max_c'], max(recues))
        self.assertLess(resultat['temperature_min_c'],
                        resultat['temperature_max_c'])

    def test_base_inconnue_refusee_en_nommant_le_champ(self):
        transport = TransportEnregistre(self.charge)
        with self.assertRaises(EntreeInvalide) as capture:
            client(transport).tmy(lat=33.5, lon=-7.6, base='PVGIS-MAROC')
        self.assertEqual(capture.exception.champ, 'base')
        self.assertEqual(transport.appels, [])

    def test_reponse_vide_refusee_sans_temperature_inventee(self):
        transport = TransportEnregistre({'outputs': {'tmy_hourly': []}})
        with self.assertRaises(PvgisIndisponible):
            client(transport).tmy(lat=33.5, lon=-7.6)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
