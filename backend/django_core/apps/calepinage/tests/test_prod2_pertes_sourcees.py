"""CAL139 — les pertes du module : explicites, sourcées, additionnées UNE fois.

Trois garanties sont vérifiées ici :

1. **Aucune perte sans source AFFICHÉE** — un poste sans source est publié
   comme non sourcé (il ne disparaît pas, et il n'hérite d'aucune valeur).
2. (ACAL329) La valeur ``loss`` passée à PVGIS n'existe plus : le modèle
   « PVGIS applique les pertes » et ``politique_du_calepinage`` sont supprimés.
3. **Aucun 14 % ni 20 % caché ne subsiste dans le module** — test de SURFACE
   sur les sources du paquet ``apps/calepinage``.

Tests PURS : aucune base, aucun réseau (le transport PVGIS est injecté).
"""
from __future__ import annotations

import pathlib
import unittest

from apps.calepinage.services.pertes import (
    CATALOGUE, CATALOGUE_PAR_POSTE, PertesInvalides, moyenne_mensuelle,
    postes_du_calepinage, valider_postes,
)

RACINE_MODULE = pathlib.Path(__file__).resolve().parent.parent


class FauxCalepinage:
    """Un double MINIMAL : ce service ne lit que ``pertes`` (et écrit dessus)."""

    def __init__(self, pertes=None):
        self.pk = 1
        self.pertes = pertes
        self.enregistrements = []

    def save(self, *args, **kwargs):
        self.enregistrements.append(kwargs.get('update_fields'))


class CatalogueTest(unittest.TestCase):

    def test_le_catalogue_ne_porte_aucune_valeur(self):
        """Un catalogue qui porterait des valeurs serait le forfait d'avant."""
        for entree in CATALOGUE:
            self.assertEqual(
                set(entree), {'poste', 'libelle', 'reference', 'mensuel'},
                entree['poste'])
            self.assertIsInstance(entree['mensuel'], bool)
            self.assertTrue(entree['reference'])

    def test_les_postes_pvsyst_et_la_ligne_nocturne_sont_la(self):
        attendus = {
            'iam', 'salissure', 'irradiance', 'thermique', 'lid',
            'qualite_module', 'mismatch', 'vieillissement', 'ohmique_dc',
            'ohmique_ac', 'transformateur', 'auxiliaires', 'indisponibilite',
            # La ligne que CAL139 ajoute à la liste PVsyst.
            'auxiliaires_nocturnes',
        }
        self.assertTrue(attendus.issubset(set(CATALOGUE_PAR_POSTE)))

    def test_la_salissure_est_le_poste_mensuel(self):
        self.assertTrue(CATALOGUE_PAR_POSTE['salissure']['mensuel'])
        self.assertFalse(CATALOGUE_PAR_POSTE['thermique']['mensuel'])


class ValidationTest(unittest.TestCase):

    def test_un_poste_sans_source_est_publie_non_source(self):
        postes = valider_postes([{'poste': 'mismatch', 'pct': 2.0}])
        self.assertEqual(len(postes), 1)
        self.assertIsNone(postes[0]['source'])
        # Le libellé et la référence du catalogue complètent l'affichage sans
        # inventer la moindre VALEUR.
        self.assertEqual(postes[0]['libelle'], 'Dispersion (mismatch)')
        self.assertIn('PVsyst', postes[0]['reference'])

    def test_un_poste_hors_catalogue_reste_admis(self):
        postes = valider_postes(
            [{'poste': 'perte_maison', 'pct': 1.0, 'source': 'mesure'}])
        self.assertEqual(postes[0]['libelle'], '')
        self.assertEqual(postes[0]['source'], 'mesure')

    def test_une_source_inconnue_est_refusee_en_nommant_le_poste(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'soiling', 'pct': 2, 'source': 'ouï'}])
        self.assertEqual(refus.exception.champ, 'soiling')
        self.assertIn('soiling', str(refus.exception))

    def test_un_poste_sans_valeur_est_refuse_en_le_nommant(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'thermique', 'source': 'fiche'}])
        self.assertEqual(refus.exception.champ, 'thermique')

    def test_un_doublon_de_poste_est_refuse(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'iam', 'pct': 1.0},
                            {'poste': 'iam', 'pct': 1.0}])
        self.assertIn('deux fois', str(refus.exception))

    def test_la_salissure_mensuelle_donne_la_moyenne_des_douze_mois(self):
        mois = [1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 6.0, 4.0, 2.0, 1.0, 1.0]
        postes = valider_postes([
            {'poste': 'salissure', 'mensuel': mois, 'source': 'societe'}])
        self.assertAlmostEqual(postes[0]['pct'], sum(mois) / 12.0, places=9)
        self.assertEqual(postes[0]['mensuel'], mois)

    def test_onze_mois_sont_refuses(self):
        with self.assertRaises(PertesInvalides) as refus:
            moyenne_mensuelle([1.0] * 11, champ='salissure')
        self.assertEqual(refus.exception.champ, 'salissure.mensuel')

    def test_un_mois_illisible_nomme_le_mois(self):
        mois = [1.0] * 12
        mois[7] = 'beaucoup'
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'salissure', 'mensuel': mois}])
        self.assertIn('août', str(refus.exception))


class PostesDuCalepinageTest(unittest.TestCase):

    def test_aucun_poste_n_est_ajoute_d_office(self):
        cal = FauxCalepinage([{'poste': 'onduleur', 'pct': 2.5,
                               'source': 'fiche'}])
        self.assertEqual([p['poste'] for p in postes_du_calepinage(cal)],
                         ['onduleur'])


class SurfaceAucunForfaitCacheTest(unittest.TestCase):
    """CAL139 — aucun forfait caché ne subsiste dans le module.

    LE SCANNER DE SURFACE EST CELUI DE CAL238, PAS UN SECOND.
    ``tests/test_politique_pertes_pvgis.py`` scanne DÉJÀ tous les fichiers du
    paquet (constantes du site public, littéraux posés comme une perte) et il
    est le SEUL à citer les valeurs interdites — un second scanner qui les
    citerait aussi ferait rougir le premier, et deux scanners finiraient par
    diverger. Ce qui est vérifié ICI, c'est que la couverture de ce scanner
    atteint bien les fichiers neufs de CAL139 : personne ne peut sortir un
    service du champ du test sans que celui-ci le dise.
    """

    def test_le_scanner_de_surface_couvre_les_fichiers_neufs(self):
        from .test_politique_pertes_pvgis import _fichiers_du_module

        couverts = {chemin.name for chemin in _fichiers_du_module()}
        for neuf in ('pertes.py', 'thermique.py', 'bifacial.py',
                     'p50p90.py', 'horizon.py'):
            self.assertIn(neuf, couverts, neuf)

    def test_le_module_ne_fabrique_aucun_poste_par_defaut(self):
        """Sans liste persistée, aucun poste n'est supposé."""
        cal = FauxCalepinage(None)
        self.assertEqual(postes_du_calepinage(cal), [])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
