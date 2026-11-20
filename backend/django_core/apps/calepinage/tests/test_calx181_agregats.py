"""CALX181 — mensuel et par pan cohérents avec la cascade, pas à côté.

`services/production.py::_agreger` construisait ses buckets depuis la
puissance `P` rendue par PVGIS — celle qui DISPARAÎT avec `pvcalculation=0`
(CALX150). Or `services/comparaison.py:32` et `services/export_csv.py:127-143`
lisent tous deux `production.mensuel` et `production.par_pan` : les deux blocs
doivent continuer d'exister, mais alimentés par la CHAÎNE.

Un seul chemin arithmétique : les douze mois, chaque pan, chaque année et le
total sortent de la MÊME boucle sur les mêmes points. La somme des mois égale
donc le total par construction — et l'arrondi ne crée pas d'écart, le reste
étant reporté sur les seaux qui en ont le plus.

Les points viennent de la réponse PVGIS enregistrée
`tests/fixtures_pvgis/seriescalc_casablanca_sud.json`. Aucune base, aucun
réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx181_agregats
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import irradiation_mensuelle
from apps.calepinage.services.chaine_pertes import (
    CLE_CASCADES_PAR_PAN, CLE_SORTIES_PAR_PAN, MOTIF_PAN_SANS_SERIE,
    appliquer_chaine, irradiation_kwh_m2,
)
from apps.calepinage.services.irradiation_mensuelle import (
    CLE_IRRADIATIONS_MENSUELLES_PAR_PAN,
)
from apps.calepinage.services.comparaison import CLES_PRODUCTION
from apps.calepinage.services.export_csv import export_csv
from apps.calepinage.services.incertitude import ORIGINE_MESUREE
from apps.calepinage.tests.test_pvgis_serie import serie_enregistree

TOLERANCE_KWH = 0.1


def points_reels(nom='seriescalc_casablanca_sud.json'):
    return serie_enregistree(nom)['points']


POINTS = points_reels()


def serie(facteur):
    """La série du fixture mise à l'échelle d'un pan — une COPIE."""
    return {'pas_minutes': 60, 'colonne_energie': 'p_w',
            'points': [dict(point,
                            p_w=(point['p_w'] * facteur
                                 if point['p_w'] is not None else None))
                       for point in POINTS]}


PLANS = [
    {'cle': 'A', 'pan': 'PAN-A', 'modules': 8, 'kwc': 4.0,
     'azimut_deg': 180.0, 'inclinaison_deg': 15.0},
    {'cle': 'B', 'pan': 'PAN-B', 'modules': 6, 'kwc': 3.0,
     'azimut_deg': 90.0, 'inclinaison_deg': 20.0},
    {'cle': 'C', 'pan': 'PAN-C', 'modules': 0, 'kwc': 0.0,
     'azimut_deg': None, 'inclinaison_deg': None},
]


def reglages(mode='pluriannuel'):
    valeurs = {'mode_meteo': {'valeur': mode, 'source': 'societe'}}
    if mode == 'pluriannuel':
        valeurs['fenetre_annees'] = {'valeur': '2020-2020',
                                     'source': 'societe'}
    return valeurs


def simuler(*, mode='pluriannuel', plans=None, sorties=True, resultat=None):
    contexte = {
        'site': {'lat': 33.5, 'lon': -7.6, 'fuseau': 'Africa/Casablanca'},
        'meteo': {'heure': {'base': 'utc'}},
        'plans': list(PLANS if plans is None else plans),
        'reglages_simulation': reglages(mode),
    }
    if sorties:
        contexte[CLE_SORTIES_PAR_PAN] = {'A': serie(4.0), 'B': serie(3.0)}
    resultat = {} if resultat is None else resultat
    appliquer_chaine(serie(1.0), contexte, resultat=resultat)
    return resultat


class TableauxCoherentsTest(unittest.TestCase):
    """La colonne ADDITIONNE ce que le total annonce."""

    def setUp(self):
        self.production = simuler()['production']

    def test_les_douze_mois_somment_le_total(self):
        somme = sum(mois['p50_kwh'] for mois in self.production['mensuel'])
        self.assertAlmostEqual(somme, self.production['total']['p50_kwh'],
                               delta=TOLERANCE_KWH)

    def test_les_pans_somment_le_total(self):
        somme = sum(ligne['p50_kwh'] for ligne in self.production['par_pan']
                    if ligne['p50_kwh'] is not None)
        self.assertAlmostEqual(somme, self.production['total']['p50_kwh'],
                               delta=TOLERANCE_KWH)

    def test_la_moyenne_des_annees_est_le_total(self):
        # ACAL54 — le P50 est l'ANNÉE MOYENNE de la fenêtre : la moyenne des
        # totaux observés (une seule année ici, donc son total).
        annees = self.production['annees']
        moyenne = sum(annee['kwh'] for annee in annees) / len(annees)
        self.assertAlmostEqual(moyenne, self.production['total']['p50_kwh'],
                               delta=TOLERANCE_KWH)
        self.assertEqual(self.production['total']['portee'], 'annee_moyenne')
        self.assertEqual(self.production['total']['annees_fenetre'],
                         len(annees))

    def test_les_douze_mois_sont_tous_la_dans_l_ordre(self):
        self.assertEqual([mois['mois'] for mois in self.production['mensuel']],
                         list(range(1, 13)))

    def test_le_total_vient_de_la_cascade_et_non_d_un_autre_calcul(self):
        # Les deux pans portent 4 et 3 fois la série de base : leur somme est
        # SEPT fois cette série, et c'est ce que le total doit dire.
        seul = simuler(plans=[dict(PLANS[0], kwc=1.0, modules=1)],
                       sorties=False)['production']
        self.assertAlmostEqual(self.production['total']['p50_kwh'],
                               seul['total']['p50_kwh'] * 7, delta=0.5)


class ClesLuesParLesConsommateursTest(unittest.TestCase):
    """Aucune clé existante n'est retirée : les deux lecteurs vivent."""

    def setUp(self):
        self.resultat = simuler()
        self.production = self.resultat['production']

    def test_les_colonnes_de_comparaison_sont_presentes(self):
        total = self.production['total']
        for cle in CLES_PRODUCTION:
            if cle == 'self_consumption_rate':
                # Celle-là vient de l'autoconsommation, pas de la chaîne.
                continue
            self.assertIn(cle, total, cle)

    def test_l_export_mensuel_sort_du_bloc_publie(self):
        document = {
            'production': self.production,
            'pertes': [], 'version_moteur': 'essai',
            'points': [], 'shading12x24': None,
        }
        texte = export_csv(document, quoi='mensuel')
        self.assertIn('mois;production_kwh', texte)
        self.assertIn('total_annuel', texte)

    def test_la_provenance_de_l_export_lit_production_base(self):
        base = self.production['base']
        for cle in ('source', 'base_rayonnement', 'fenetre_annees',
                    'loss_passee_pct', 'commentaire'):
            self.assertIn(cle, base, cle)

    def test_aucune_perte_n_est_passee_a_pvgis(self):
        self.assertIsNone(
            self.production['base']['loss_passee_pct'],
            "D-CALX 4 : avec pvcalculation=0 aucune perte ne part dans la "
            "requête — un 0 se lirait « zéro perte annoncée ».")

    def test_les_colonnes_d_une_ligne_de_pan_sont_inchangees(self):
        attendues = {'pan', 'modules', 'kwc', 'azimut_deg', 'inclinaison_deg',
                     'p50_kwh', 'p75_kwh', 'p90_kwh', 'performance_ratio',
                     'specific_yield_kwh_kwc', 'shading_annual_loss_pct',
                     # CALX58 — cinq colonnes d'ORIENTATION, que le contrat
                     # de simulation décrit et que la chaîne publie ; nulles
                     # ici, faute de client PVGIS dans le harnais.
                     'tof', 'tsrf', 'inclinaison_optimale_deg',
                     'azimut_optimal_deg', 'source'}
        for ligne in self.production['par_pan']:
            self.assertEqual(set(ligne), attendues, ligne['pan'])


class PanVideTest(unittest.TestCase):
    """Un pan sans module rend `null`, jamais 0."""

    def test_le_pan_sans_module_garde_ses_cles_a_null(self):
        production = simuler()['production']
        vide = [ligne for ligne in production['par_pan']
                if ligne['pan'] == 'PAN-C'][0]
        self.assertEqual(vide['modules'], 0)
        for cle in ('p50_kwh', 'p75_kwh', 'p90_kwh', 'performance_ratio',
                    'specific_yield_kwh_kwc', 'shading_annual_loss_pct'):
            self.assertIsNone(vide[cle], cle)

    def test_sans_serie_par_pan_les_lignes_restent_vides_et_le_disent(self):
        resultat = simuler(sorties=False)
        production = resultat['production']
        for ligne in production['par_pan']:
            self.assertIsNone(ligne['p50_kwh'], ligne['pan'])
        self.assertIsNotNone(production['total']['p50_kwh'])
        self.assertIn(MOTIF_PAN_SANS_SERIE, resultat['avertissements'])

    def test_une_serie_sans_colonne_d_energie_publie_des_nuls(self):
        contexte = {
            'site': {'lat': 33.5, 'lon': -7.6},
            'plans': [],
            'reglages_simulation': reglages(),
        }
        resultat = {}
        appliquer_chaine({'pas_minutes': 60, 'points': [{'t2m_c': 21.0}]},
                         contexte, resultat=resultat)
        total = resultat['production']['total']
        self.assertIsNone(total['p50_kwh'])
        for mois in resultat['production']['mensuel']:
            self.assertIsNone(mois['p50_kwh'])


class ModeTmyTest(unittest.TestCase):
    """CALX153 — en année météo type, aucun total annuel observé."""

    def test_aucune_annee_n_est_publiee_et_sigma_n_est_pas_mesure(self):
        production = simuler(mode='tmy')['production']
        self.assertEqual(production['annees'], [])
        self.assertNotEqual(production['total']['annual_variability_source'],
                            ORIGINE_MESUREE)

    def test_en_pluriannuel_l_annee_reellement_couverte_est_publiee(self):
        production = simuler()['production']
        self.assertEqual([annee['annee'] for annee in production['annees']],
                         [2020])


class IrradiationMensuelleTest(unittest.TestCase):
    """ACAL451 — l'irradiation incidente mensuelle somme l'annuelle servie."""

    @staticmethod
    def _serie_gi(facteur):
        """La série du fixture dont l'irradiance est mise à l'échelle."""
        copie = serie(1.0)
        for point in copie['points']:
            if point['gi_w_m2'] is not None:
                point['gi_w_m2'] = point['gi_w_m2'] * facteur
        return copie

    def _contexte(self, plans, sorties=None):
        contexte = {
            'site': {'lat': 33.5, 'lon': -7.6, 'fuseau': 'Africa/Casablanca'},
            'meteo': {'heure': {'base': 'utc'}},
            'plans': plans,
            'reglages_simulation': reglages(),
        }
        if sorties:
            contexte[CLE_SORTIES_PAR_PAN] = sorties
        return contexte

    def test_un_pan_les_douze_mois_somment_l_irradiation_de_la_cascade(self):
        resultat = {}
        _serie, cascade = appliquer_chaine(
            serie(1.0), self._contexte([dict(PLANS[0], kwc=1.0, modules=1)]),
            resultat=resultat)
        lignes = resultat['production']['irradiation_mensuelle']

        self.assertEqual([ligne['mois'] for ligne in lignes],
                         list(range(1, 13)))
        self.assertAlmostEqual(
            sum(ligne['irradiation_plan_kwh_m2'] for ligne in lignes),
            cascade['irradiation_incidente_kwh_m2'], delta=0.0065)
        self.assertGreater(lignes[6]['irradiation_plan_kwh_m2'], 0.0)

    def test_deux_pans_de_kwc_differents_sont_ponderes_par_le_kwc(self):
        serie_a, serie_b = self._serie_gi(1.0), self._serie_gi(0.5)
        irr_a = irradiation_kwh_m2(serie_a)
        irr_b = irradiation_kwh_m2(serie_b)
        contexte = self._contexte(
            PLANS[:2], {'A': serie(4.0), 'B': serie(3.0)})
        contexte[CLE_CASCADES_PAR_PAN] = {
            'A': {'irradiation_incidente_kwh_m2': irr_a},
            'B': {'irradiation_incidente_kwh_m2': irr_b}}
        contexte[CLE_IRRADIATIONS_MENSUELLES_PAR_PAN] = {
            'A': irradiation_mensuelle.par_mois(serie_a),
            'B': irradiation_mensuelle.par_mois(serie_b)}
        resultat = {}
        appliquer_chaine(serie(1.0), contexte, resultat=resultat)
        somme = sum(ligne['irradiation_plan_kwh_m2'] for ligne
                    in resultat['production']['irradiation_mensuelle'])

        # (4 x irr_a + 3 x irr_b) / 7 : le même poids que l'annuelle.
        attendue = (4.0 * irr_a + 3.0 * irr_b) / 7.0
        self.assertAlmostEqual(somme, attendue, delta=0.0065)
        self.assertGreater(abs(somme - (irr_a + irr_b) / 2.0), 1.0)

    def test_un_mois_sans_point_vaut_null_jamais_zero(self):
        mensuelle = irradiation_mensuelle.par_mois(
            {'pas_minutes': 60, 'points': [
                {'mois': 3, 'gi_w_m2': 1000.0}]})

        self.assertEqual(mensuelle[3], 1.0)
        self.assertIsNone(mensuelle[1])
        lignes = irradiation_mensuelle.publier(
            irradiation_mensuelle.ponderer([mensuelle], [2.0]), 1)
        self.assertIsNone(lignes[0]['irradiation_plan_kwh_m2'])
        self.assertEqual(lignes[2]['irradiation_plan_kwh_m2'], 1.0)

    def test_sans_simulation_la_liste_est_vide(self):
        self.assertEqual(irradiation_mensuelle.publier(None, 1), [])


if __name__ == '__main__':
    unittest.main()
