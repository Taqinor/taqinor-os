"""CALX142 — la série horaire persistée est ADDITIVE : l'export ne bouge pas.

La preuve est faite par l'exporteur lui-même : l'exemple committé est passé à
``services/export_csv.export_csv(quoi='horaire')`` et le fichier produit est
comparé ligne à ligne. Les sept colonnes lues depuis CAL144 sortent
inchangées, et AUCUNE des treize colonnes ajoutées ne fuit dans le CSV.

Le reste garde les deux disciplines du bloc : une colonne non produite vaut
``null`` sur tous les points (jamais ``0``, qui se lirait « mesuré à zéro »),
et les colonnes qui décrivent la même grandeur ne peuvent pas diverger
(``p_w`` vaut mille fois ``p_ac_kw`` ; l'écrêtage ne dépasse pas l'écart entre
continu et alternatif).

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx142_contrat_serie
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.export_csv import export_csv

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


SERIE = charger('calepinage_serie_horaire.json')
SIMULATION = charger('calepinage_simulation.json')

#: Les sept colonnes que `services/export_csv.py:102-124` lit depuis CAL144.
HISTORIQUES = ('annee', 'mois', 'jour', 'heure', 'p_w', 'gi_w_m2', 't2m_c')

#: Les treize colonnes ADDITIVES déclarées par CALX142.
ADDITIVES = ('ws10m', 'h_sun_deg', 'gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2',
             't_cell_c', 'p_dc_kw', 'p_ac_kw', 'ecretage_kw', 'charge_kwh',
             'batterie_soc_pct', 'reseau_import_kwh', 'reseau_export_kwh')

#: Les états qui portent une série non vide.
ETATS_SERVIS = ('exemple', 'exemple_tronquee')


def bloc(etat):
    return SERIE[etat]['serie_horaire']


class EnveloppeTest(unittest.TestCase):
    """L'échantillon se relit, et ses états portent les mêmes clés."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, SERIE)
        self.assertIn('export-csv/', SERIE['endpoint'])

    def test_memes_clefs_que_le_bloc_serie_horaire_de_calx4(self):
        attendu = sorted(SIMULATION['exemple']['serie_horaire'])
        for etat in ETATS_SERVIS + ('exemple_vide',):
            self.assertEqual(sorted(bloc(etat)), attendu,
                             f'{etat} : les clés du bloc ont divergé de '
                             'calepinage_simulation.json (CALX4).')

    def test_vide_ne_publie_aucun_zero(self):
        vide = bloc('exemple_vide')
        self.assertIsNone(vide['pas_minutes'])
        self.assertIsNone(vide['tronquee'])
        self.assertEqual(vide['colonnes'], [])
        self.assertEqual(vide['points'], [])


class ColonnesTest(unittest.TestCase):
    """Sept colonnes historiques figées, treize ajoutées à côté."""

    def test_chaque_point_porte_les_vingt_colonnes(self):
        attendu = set(HISTORIQUES) | set(ADDITIVES)
        for etat in ETATS_SERVIS:
            for point in bloc(etat)['points']:
                self.assertEqual(
                    set(point), attendu,
                    f'{etat} : un point en écart de '
                    f'{sorted(set(point) ^ attendu)}. Une colonne absente '
                    'reste PRÉSENTE à null — un écran qui reçoit parfois une '
                    "clé et parfois pas finit par tester l'absence de clé.")

    def test_les_sept_historiques_ouvrent_la_liste_des_colonnes(self):
        for etat in ETATS_SERVIS:
            self.assertEqual(tuple(bloc(etat)['colonnes'][:7]), HISTORIQUES,
                             f'{etat} : les colonnes de CAL144 ne bougent '
                             "ni de nom ni de rang.")

    def test_une_colonne_non_produite_est_nulle_partout(self):
        for etat in ETATS_SERVIS:
            produites = set(bloc(etat)['colonnes'])
            absentes = (set(HISTORIQUES) | set(ADDITIVES)) - produites
            for point in bloc(etat)['points']:
                for colonne in sorted(absentes):
                    self.assertIsNone(
                        point[colonne],
                        f'{etat} : « {colonne} » ne figure pas dans '
                        '`colonnes` mais vaut '
                        f'{point[colonne]!r} — un 0 se lirait « mesuré à '
                        'zéro ».')
                for colonne in sorted(produites):
                    self.assertIsNotNone(
                        point[colonne],
                        f'{etat} : « {colonne} » est annoncée produite et '
                        'vaut null sur un point.')


class CoherenceDesGrandeursTest(unittest.TestCase):
    """Deux colonnes qui décrivent la même chose ne peuvent pas diverger."""

    def test_p_w_vaut_mille_fois_la_puissance_alternative(self):
        for etat in ETATS_SERVIS:
            for point in bloc(etat)['points']:
                if point['p_ac_kw'] is None or point['p_w'] is None:
                    continue
                self.assertAlmostEqual(
                    point['p_w'], point['p_ac_kw'] * 1000.0, places=3,
                    msg=f"{etat} : à {point['heure']} h, la colonne "
                        "historique `p_w` (W) et `p_ac_kw` (kW) racontent "
                        'deux productions différentes.')

    def test_l_ecretage_ne_depasse_pas_l_ecart_continu_alternatif(self):
        for etat in ETATS_SERVIS:
            for point in bloc(etat)['points']:
                trio = (point['p_dc_kw'], point['p_ac_kw'],
                        point['ecretage_kw'])
                if any(valeur is None for valeur in trio):
                    continue
                continu, alternatif, ecrete = trio
                self.assertLessEqual(
                    ecrete, continu - alternatif + 1e-9,
                    f"{etat} : à {point['heure']} h, l'écrêtage dépasse "
                    "l'écart entre continu et alternatif — or la conversion "
                    "de l'onduleur en prend aussi sa part.")

    def test_les_trois_composantes_somment_l_irradiance_du_plan(self):
        for etat in ETATS_SERVIS:
            for point in bloc(etat)['points']:
                composantes = (point['gb_i_w_m2'], point['gd_i_w_m2'],
                               point['gr_i_w_m2'])
                if any(valeur is None for valeur in composantes):
                    continue
                self.assertAlmostEqual(sum(composantes), point['gi_w_m2'],
                                       places=3, msg=etat)


class PointsExigesParLePlanTest(unittest.TestCase):
    """L'exemple porte un point NOCTURNE et un point ÉCRÊTÉ."""

    def test_un_point_nocturne(self):
        nocturnes = [p for p in bloc('exemple')['points']
                     if p['h_sun_deg'] is not None and p['h_sun_deg'] < 0]
        self.assertTrue(nocturnes, "L'exemple doit porter une heure de nuit.")
        for point in nocturnes:
            self.assertEqual(point['gi_w_m2'], 0.0)
            self.assertEqual(point['p_w'], 0.0,
                             'La nuit, 0 est une valeur MESURÉE — pas une '
                             'colonne absente.')

    def test_un_point_ecrete(self):
        ecretes = [p for p in bloc('exemple')['points']
                   if (p['ecretage_kw'] or 0.0) > 0.0]
        self.assertTrue(ecretes, "L'exemple doit porter une heure écrêtée.")
        for point in ecretes:
            self.assertGreater(point['p_dc_kw'], point['p_ac_kw'])


class ExportInchangeTest(unittest.TestCase):
    """CAL144 sort EXACTEMENT ce qu'il sortait : c'est le sens d'« additif »."""

    def _csv(self, etat):
        # Le document d'export tel que `views/export_csv.document_exportable`
        # le compose, à ceci près qu'il reçoit la LISTE de points : le bloc
        # étant un objet depuis CALX4, la vue devra lire `serie_horaire.points`
        # le jour où la simulation écrira la clé (signalé dans le contrat).
        document = {
            'production': {'base': {}},
            'pertes': [],
            'points': bloc(etat)['points'],
            'shading12x24': None,
            'version_moteur': None,
        }
        return export_csv(document, quoi='horaire')

    def test_l_entete_des_colonnes_est_celui_de_cal144(self):
        texte = self._csv('exemple')
        self.assertIn('annee;mois;jour;heure;production_kw;'
                      'irradiance_plan_w_m2;temperature_air_c', texte)

    def test_les_lignes_sortent_inchangees(self):
        texte = self._csv('exemple')
        for ligne in ('2020;1;15;3;0,000;0,00;11,40',
                      '2020;1;15;13;6,800;880,00;19,80',
                      '2020;7;15;12;8,000;1020,00;33,50'):
            self.assertIn(ligne, texte,
                          'La ligne historique a bougé : les sept colonnes '
                          'de CAL144 sont figées.')

    def test_aucune_colonne_additive_ne_fuit_dans_le_csv(self):
        texte = self._csv('exemple_tronquee')
        for colonne in ADDITIVES:
            self.assertNotIn(colonne, texte,
                             f'« {colonne} » apparaît dans un export qui ne '
                             'la lit pas : l’ajout n’est plus additif.')


if __name__ == '__main__':
    unittest.main()
