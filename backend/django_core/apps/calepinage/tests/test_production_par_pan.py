"""CAL138 — la production se calcule PAR PAN, jamais sur un azimut moyen.

Les trois séries rejouées (sud, est, ouest) sont des réponses PVGIS RÉELLES
enregistrées le 20/09/2026 au même point, même pente, même fenêtre : seul
l'azimut change. C'est ce qui permet de comparer honnêtement « deux pans
opposés » à « leur moyenne » sans fabriquer une seule irradiation.
"""
from __future__ import annotations

import json
import unittest

from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.production import (
    PanSansOrientation, pans_du_layout, production_du_layout,
)
from apps.calepinage.services.pvgis_serie import _Cache, ClientPvgis
from apps.calepinage.tests.test_pvgis_serie import POSTES_ESSAI, charger

#: Azimuts de FACE du document de toiture (0 = Nord, 180 = Sud).
SUD, EST, OUEST = 180.0, 90.0, 270.0


class TransportParOrientation:
    """Rejoue la fixture correspondant à l'``aspect`` demandé dans l'URL."""

    FIXTURES = {
        '0': 'seriescalc_casablanca_sud.json',
        '-90': 'seriescalc_casablanca_est.json',
        '90': 'seriescalc_casablanca_ouest.json',
    }

    def __init__(self):
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        aspect = url.split('aspect=')[1].split('&')[0]
        aspect = aspect.replace('%2D', '-')
        nom = self.FIXTURES.get(str(int(float(aspect))))
        if nom is None:  # pragma: no cover - garde de test
            raise AssertionError(f'Aucune fixture pour aspect={aspect}')
        return 200, json.dumps(charger(nom))


def zone(nom, *, modules, kwc, azimut, pente=15.0):
    return {'id': nom, 'label': nom,
            'geometry': {'azimuthDeg': azimut, 'tiltDeg': pente,
                         'count': modules, 'kwc': kwc}}


def calculer(zones, transport=None):
    transport = transport or TransportParOrientation()
    client = ClientPvgis(transport, cache=_Cache(), dormir=lambda _s: None)
    resultat = production_du_layout(
        {'version': 2, 'zones': zones}, lat=33.5, lon=-7.6,
        politique=politique_de_pertes(POSTES_ESSAI), client=client,
        annee_debut=2020, annee_fin=2020)
    return resultat, transport


class ProductionParPanTest(unittest.TestCase):

    def test_chaque_pan_est_interroge_a_son_propre_azimut(self):
        resultat, transport = calculer([
            zone('PAN-EST', modules=8, kwc=5.76, azimut=EST),
            zone('PAN-OUEST', modules=4, kwc=2.88, azimut=OUEST),
        ])
        aspects = sorted(url.split('aspect=')[1].split('&')[0]
                         for url in transport.appels)
        self.assertEqual(len(transport.appels), 2)
        self.assertEqual(aspects, ['-90.0', '90.0'])

        par_pan = {ligne['pan']: ligne for ligne in
                   resultat['production']['par_pan']}
        self.assertEqual(set(par_pan), {'PAN-EST', 'PAN-OUEST'})
        for ligne in par_pan.values():
            self.assertGreater(ligne['p50_kwh'], 0)
            self.assertGreater(ligne['performance_ratio'], 0)

    def test_le_total_est_exactement_la_somme_des_pans(self):
        resultat, _ = calculer([
            zone('PAN-EST', modules=8, kwc=5.76, azimut=EST),
            zone('PAN-OUEST', modules=4, kwc=2.88, azimut=OUEST),
        ])
        production = resultat['production']
        somme = sum(ligne['p50_kwh'] for ligne in production['par_pan'])
        self.assertAlmostEqual(production['total']['p50_kwh'], somme, places=0)
        self.assertAlmostEqual(production['total']['kwc'], 8.64, places=3)
        # Le mensuel porte les 12 mois et retombe sur le total.
        self.assertEqual([m['mois'] for m in production['mensuel']],
                         list(range(1, 13)))
        self.assertAlmostEqual(
            sum(m['p50_kwh'] for m in production['mensuel']),
            production['total']['p50_kwh'], places=0)

    def test_deux_pans_opposes_ne_valent_pas_leur_azimut_moyen(self):
        """Le cœur de CAL138 : la moyenne est un toit qui n'existe pas."""
        deux_pans, _ = calculer([
            zone('PAN-EST', modules=6, kwc=4.32, azimut=EST),
            zone('PAN-OUEST', modules=6, kwc=4.32, azimut=OUEST),
        ])
        # « Moyenne » des azimuts de face 90 et 270 en passant par le sud :
        # un pan unique de même puissance totale, orienté 180.
        moyenne, _ = calculer([
            zone('PAN-MOYEN', modules=12, kwc=8.64, azimut=SUD),
        ])
        self.assertNotAlmostEqual(
            deux_pans['production']['total']['p50_kwh'],
            moyenne['production']['total']['p50_kwh'], places=0)
        # Et l'écart n'est pas un détail : le sud produit franchement plus.
        self.assertGreater(moyenne['production']['total']['p50_kwh'],
                           deux_pans['production']['total']['p50_kwh'])

    def test_un_pan_sans_module_ne_pese_rien_et_ne_vaut_pas_zero_kwh(self):
        resultat, transport = calculer([
            zone('PAN-SUD', modules=12, kwc=8.64, azimut=SUD),
            zone('PAN-VIDE', modules=0, kwc=0, azimut=EST),
        ])
        self.assertEqual(len(transport.appels), 1)  # aucun appel pour le vide
        vide = [ligne for ligne in resultat['production']['par_pan']
                if ligne['pan'] == 'PAN-VIDE'][0]
        self.assertEqual(vide['modules'], 0)
        self.assertIsNone(vide['p50_kwh'])  # jamais 0.0
        self.assertTrue(any('PAN-VIDE' in avis
                            for avis in resultat['avertissements']))

    def test_pan_avec_modules_sans_orientation_refuse_en_le_nommant(self):
        with self.assertRaises(PanSansOrientation) as capture:
            calculer([{'id': 'PAN-X', 'label': 'PAN-X',
                       'geometry': {'count': 8, 'kwc': 5.76}}])
        self.assertIn('PAN-X', str(capture.exception))
        self.assertIn('PAN-X', capture.exception.champ)

    def test_la_provenance_et_les_pertes_accompagnent_le_chiffre(self):
        resultat, _ = calculer([
            zone('PAN-SUD', modules=12, kwc=8.64, azimut=SUD)])
        base = resultat['production']['base']
        self.assertEqual(base['source'], 'pvgis')
        self.assertEqual(base['base_rayonnement'], 'PVGIS-SARAH3')
        self.assertEqual(base['fenetre_annees'], '2020-2020')
        self.assertEqual(base['loss_passee_pct'],
                         sum(poste['pct'] for poste in POSTES_ESSAI))
        self.assertEqual([poste['poste'] for poste in resultat['pertes']],
                         [poste['poste'] for poste in POSTES_ESSAI])

    def test_p75_p90_et_variabilite_restent_non_calcules(self):
        resultat, _ = calculer([
            zone('PAN-SUD', modules=12, kwc=8.64, azimut=SUD)])
        total = resultat['production']['total']
        self.assertIsNone(total['p75_kwh'])
        self.assertIsNone(total['p90_kwh'])
        self.assertIsNone(total['annual_variability'])
        self.assertTrue(any('CAL142' in avis
                            for avis in resultat['avertissements']))


class LecturePansTest(unittest.TestCase):
    """La lecture du document ne suppose rien qu'il ne dise pas."""

    def test_la_geometrie_posee_prime_sur_le_resultat_decran(self):
        pans = pans_du_layout({'zones': [{
            'id': 'z1', 'label': 'Pan Sud', 'pitchDeg': 20.0,
            'facingAzimuthDeg': 170.0,
            'result': {'count': 4, 'kwc': 2.88},
            'geometry': {'count': 12, 'kwc': 8.64, 'azimuthDeg': 180.0,
                         'tiltDeg': 15.0},
        }]})
        self.assertEqual(pans, [{
            'pan': 'Pan Sud', 'modules': 12, 'kwc': 8.64,
            'azimut_deg': 180.0, 'inclinaison_deg': 15.0}])

    def test_document_sans_zone_ne_rend_aucun_pan(self):
        self.assertEqual(pans_du_layout({}), [])
        self.assertEqual(pans_du_layout(None), [])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
