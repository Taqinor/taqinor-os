"""CAL164 — masse installée et surcharge de toiture, depuis les FICHES.

Les trois garanties du « Done » :

1. une fiche SANS ``poids_kg`` ⇒ la masse n'est PAS publiée pour ce produit,
   qui est LISTÉ comme manquant (jamais un poids de catalogue « moyen ») ;
2. la masse par m² se calcule sur la surface RÉELLE DU PAN (``result.areaM2``
   du document), jamais sur l'emprise du bâtiment — et un pan sans surface
   connue ne publie pas de masse/m², en le disant ;
3. chaque ligne cite le poids unitaire employé et son ORIGINE.

Tests PURS : aucune base de données (le document ``roof_layout`` et les cotes
de fiche sont passés à la main, exactement comme les rendrait
``apps.stock.selectors.dimensions_de_pose``).
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.lestage import (
    masse_du_layout,
    normaliser_section_lestage,
    surface_module_m2,
)

#: Deux pans DE SURFACES DIFFÉRENTES : c'est ce qui prouve que la masse par m²
#: suit la surface du PAN et non une emprise unique de bâtiment.
LAYOUT = {
    'version': 2,
    'zones': [
        {'id': 'z1', 'label': 'Pan Sud',
         'result': {'count': 10, 'areaM2': 20.0}},
        {'id': 'z2', 'label': 'Pan Nord',
         'result': {'count': 5, 'areaM2': 50.0}},
    ],
}

SECTION_STRUCTURE = normaliser_section_lestage({
    'masse_structure_kg_par_module': {
        'valeur': 3.0,
        'source': "Fiche du kit de pose, masse saisie par la société"},
})


def _pan(resultat, libelle):
    return next(p for p in resultat['pans'] if p['pan'] == libelle)


class MasseDepuisLaFicheTest(unittest.TestCase):

    def test_masse_par_pan_et_par_m2(self):
        resultat = masse_du_layout(LAYOUT, poids_module_kg=22.0,
                                   designation_module='Module d’essai 550 Wc',
                                   section=SECTION_STRUCTURE)
        sud = _pan(resultat, 'Pan Sud')
        # 10 modules × 22 kg = 220 kg ; structure 10 × 3 = 30 kg ⇒ 250 kg
        self.assertAlmostEqual(sud['masse_modules_kg'], 220.0)
        self.assertAlmostEqual(sud['masse_structure_kg'], 30.0)
        self.assertAlmostEqual(sud['masse_kg'], 250.0)
        # 250 kg sur 20 m² de PAN (pas sur l'emprise du bâtiment) = 12,5 kg/m²
        self.assertAlmostEqual(sud['masse_par_m2_kg'], 12.5)

        nord = _pan(resultat, 'Pan Nord')
        self.assertAlmostEqual(nord['masse_kg'], 125.0)
        self.assertAlmostEqual(nord['masse_par_m2_kg'], 2.5)
        self.assertNotAlmostEqual(sud['masse_par_m2_kg'],
                                  nord['masse_par_m2_kg'])

        self.assertEqual(resultat['total_modules'], 15)
        self.assertAlmostEqual(resultat['masse_totale_kg'], 375.0)

    def test_poids_unitaire_et_son_origine_sont_cites(self):
        resultat = masse_du_layout(LAYOUT, poids_module_kg=22.0,
                                   designation_module='Module d’essai',
                                   section=SECTION_STRUCTURE)
        unitaire = resultat['poids_unitaire']
        self.assertAlmostEqual(unitaire['module_kg'], 22.0)
        self.assertEqual(unitaire['module_source'], 'fiche produit')
        self.assertEqual(unitaire['module_designation'], 'Module d’essai')
        self.assertAlmostEqual(unitaire['structure_kg_par_module'], 3.0)
        self.assertIn('saisie par la société', unitaire['structure_source'])


class FicheSansPoidsTest(unittest.TestCase):

    def test_masse_non_publiee_et_produit_liste_manquant(self):
        resultat = masse_du_layout(LAYOUT, poids_module_kg=None,
                                   designation_module='Module sans poids',
                                   section=SECTION_STRUCTURE)
        for pan in resultat['pans']:
            self.assertIsNone(pan['masse_kg'], pan['pan'])
            self.assertIsNone(pan['masse_par_m2_kg'], pan['pan'])
            self.assertIn('poids unitaire', pan['mention'])
        self.assertIsNone(resultat['masse_totale_kg'])
        manquant = next(m for m in resultat['manquants']
                        if m['quoi'] == 'poids_module')
        self.assertEqual(manquant['libelle'], 'Module sans poids')
        self.assertIn('poids_kg', manquant['message'])

    def test_structure_non_saisie_listee_manquante(self):
        resultat = masse_du_layout(LAYOUT, poids_module_kg=22.0, section={})
        self.assertIn('masse_structure',
                      [m['quoi'] for m in resultat['manquants']])
        sud = _pan(resultat, 'Pan Sud')
        self.assertIsNone(sud['masse_structure_kg'])
        # La masse des modules, elle, reste publiée : ce qui manque est nommé,
        # ce qui est connu est servi.
        self.assertAlmostEqual(sud['masse_kg'], 220.0)


class SurfaceDuPanTest(unittest.TestCase):

    def test_pan_sans_surface_ne_publie_pas_de_masse_par_m2(self):
        layout = {'version': 2, 'zones': [
            {'id': 'z1', 'label': 'Pan sans aire', 'result': {'count': 8}}]}
        resultat = masse_du_layout(layout, poids_module_kg=22.0, section={})
        pan = _pan(resultat, 'Pan sans aire')
        self.assertIsNone(pan['surface_pan_m2'])
        self.assertIsNone(pan['masse_par_m2_kg'])
        self.assertIn('surface de ce pan', pan['mention'])

    def test_surface_nulle_traitee_comme_inconnue(self):
        layout = {'version': 2, 'zones': [
            {'id': 'z1', 'label': 'Pan plat',
             'result': {'count': 2, 'areaM2': 0}}]}
        resultat = masse_du_layout(layout, poids_module_kg=22.0, section={})
        self.assertIsNone(_pan(resultat, 'Pan plat')['masse_par_m2_kg'])

    def test_document_vide_ne_publie_rien(self):
        resultat = masse_du_layout(None, poids_module_kg=22.0, section={})
        self.assertEqual(resultat['pans'], [])
        self.assertEqual(resultat['total_modules'], 0)
        self.assertIsNone(resultat['masse_totale_kg'])


class SurfaceModuleTest(unittest.TestCase):

    def test_surface_depuis_les_cotes_de_pose(self):
        self.assertAlmostEqual(
            surface_module_m2({'longueur_mm': 2278, 'largeur_mm': 1134}),
            2.278 * 1.134)

    def test_cote_manquante_pas_de_surface(self):
        self.assertIsNone(surface_module_m2({'longueur_mm': 2278}))
        self.assertIsNone(surface_module_m2({}))
        self.assertIsNone(surface_module_m2(None))
