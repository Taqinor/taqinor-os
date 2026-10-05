"""CIQ109 — production horaire C&I par la MÊME chaîne PVGIS que le résidentiel.

Les sources PVGIS sont résolues par VILLE (tables vendorisées de
``pvgis_profils``) : aucun appel réseau. Les tests purs tournent sans
Django ; la parité avec ``etude_horaire`` importe ce module à la demande.
"""

import ast
import datetime
import os
import unittest

from apps.parametres.pvgis_profils import (
    PVGIS_ANGLE_DEG,
    PVGIS_ASPECT_DEG,
    SAISONS,
    productible_mensuel,
    profil_production_journalier,
    vers_heure_locale,
)
from apps.ventes.moteur_ci import production as module_production
from apps.ventes.moteur_ci.production import (
    MESSAGE_ORIENTATION,
    bloc_production_ci,
    production_jours_types,
)
from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE

COORDS = {'lat': None, 'lon': None, 'date_appel': '2026-10-05'}


def _sources(ville):
    """Les MÊMES sources que ``etude_horaire._formes_production_par_saison``."""
    formes = {}
    for saison in SAISONS:
        resolu = profil_production_journalier(saison=saison, ville=ville)
        if resolu:
            formes[saison] = vers_heure_locale(resolu[0])
    mensuel, source = productible_mensuel(ville=ville)
    return mensuel, formes, source


def _bloc(ville, **kwargs):
    mensuel, formes, source = _sources(ville)
    return bloc_production_ci(productible_mensuel=mensuel, formes_saison=formes,
                              derate=PRODUCTION_DERATE, coordonnees_figees=COORDS,
                              source=source, **kwargs)


class TestProductionCI(unittest.TestCase):

    def test_meme_chaine_que_le_residentiel(self):
        mensuel, formes, _source = _sources('Casablanca')
        par_mois = production_jours_types(37.5, productible_mensuel=mensuel,
                                          formes_saison=formes, derate=PRODUCTION_DERATE)
        attendu = sum(v for v in mensuel) * 37.5 * PRODUCTION_DERATE
        self.assertAlmostEqual(sum(m['prod_mois_kwh'] for m in par_mois), attendu, places=6)
        for m in par_mois:
            # formes PVGIS arrondies à 5 décimales (``_normaliser_forme``) : Σ ≈ 1 à 1e-4 près
            self.assertAlmostEqual(sum(m['prod_24h']) / m['prod_jour_kwh'], 1.0, delta=1e-4)

    def test_bloc_contrat_par_kwc(self):
        production, hypotheses, alertes = _bloc('Casablanca')
        self.assertEqual(production['source'], 'pvgis')
        self.assertEqual(production['inclinaison_deg'], PVGIS_ANGLE_DEG)
        self.assertEqual(production['azimut_deg'], PVGIS_ASPECT_DEG)
        self.assertEqual(production['coordonnees_figees'], COORDS)
        self.assertEqual(len(production['kwh_kwc_mensuel']), 12)
        self.assertEqual([j['mois'] for j in production['jours_types']], list(range(1, 13)))
        self.assertTrue(all(len(j['production_kwh_kwc']) == 24 for j in production['jours_types']))
        cles = {h['cle'] for h in hypotheses}
        self.assertTrue({'inclinaison_deg', 'azimut_deg'} <= cles)
        self.assertEqual(alertes, [])

    def test_agadir_differe_de_casablanca(self):
        agadir, _h, _a = _bloc('Agadir')
        casa, _h, _a = _bloc('Casablanca')
        self.assertNotEqual(agadir['kwh_kwc_mensuel'], casa['kwh_kwc_mensuel'])
        self.assertNotAlmostEqual(sum(agadir['kwh_kwc_mensuel']), sum(casa['kwh_kwc_mensuel']))

    def test_pvgis_indisponible_null_et_avertissement(self):
        production, _h, alertes = bloc_production_ci(
            productible_mensuel=None, formes_saison={}, derate=PRODUCTION_DERATE,
            coordonnees_figees=COORDS)
        self.assertIsNone(production)
        self.assertEqual(alertes[0]['code'], 'production_indisponible')
        # une saison sans forme : jamais une cloche inventée
        mensuel, formes, _s = _sources('Casablanca')
        formes.pop('ete')
        production, _h, alertes = bloc_production_ci(
            productible_mensuel=mensuel, formes_saison=formes, derate=PRODUCTION_DERATE,
            coordonnees_figees=COORDS)
        self.assertIsNone(production)

    def test_azimut_declare_90_production_inchangee_et_alerte(self):
        reference, _h, _a = _bloc('Casablanca')
        production, _h, alertes = _bloc('Casablanca', toit={'azimut_deg': 90, 'pente_deg': 30})
        self.assertEqual(production['kwh_kwc_mensuel'], reference['kwh_kwc_mensuel'])
        self.assertEqual(production['jours_types'], reference['jours_types'])
        orientation = [a for a in alertes if a['code'] == 'orientation_non_prise_en_compte']
        self.assertEqual(len(orientation), 1)
        self.assertEqual(orientation[0]['message'], MESSAGE_ORIENTATION)

    def test_bac_acier_sans_calepinage_a_confirmer(self):
        _p, _h, alertes = _bloc('Casablanca', toit={'type_pose': 'bac_acier'})
        self.assertIn('production_a_confirmer_calepinage', {a['code'] for a in alertes})

    def test_calepinage_passe_devant(self):
        mensuel_cal = [100.0] * 12
        production, _h, alertes = _bloc('Casablanca', toit={'azimut_deg': 90},
                                        calepinage={'id': 7, 'kwh_kwc_mensuel': mensuel_cal})
        self.assertEqual(production['source'], 'calepinage')
        self.assertEqual(production['kwh_kwc_mensuel'], mensuel_cal)
        janvier = production['jours_types'][0]['production_kwh_kwc']
        self.assertAlmostEqual(sum(janvier) / (100.0 / 31), 1.0, delta=1e-4)
        self.assertNotIn('orientation_non_prise_en_compte', {a['code'] for a in alertes})


class TestPariteResidentiel(unittest.TestCase):
    """Même ville et même kWc → même production annuelle que le résidentiel."""

    def test_meme_annuelle_que_production_annuelle_pour_kwc(self):
        try:
            from apps.ventes.etude_horaire import production_annuelle_pour_kwc
        except ImportError as exc:      # hors image Django : dépendances absentes
            self.skipTest(f'etude_horaire non importable ici : {exc}')
        for ville in ('Casablanca', 'Agadir', 'Marrakech'):
            production, _h, _a = _bloc(ville)
            kwc = 42.0
            annuelle = sum(production['kwh_kwc_mensuel']) * kwc
            self.assertEqual(round(annuelle), production_annuelle_pour_kwc(kwc, ville=ville), ville)

    def test_jours_types_annee_lit_la_fonction_partagee(self):
        try:
            from apps.ventes import etude_horaire
        except ImportError as exc:
            self.skipTest(f'etude_horaire non importable ici : {exc}')
        self.assertIs(etude_horaire.production_jours_types, production_jours_types)
        jours, _av, _src = etude_horaire.jours_types_annee(
            kwc=10, conso_kwh_mensuelles=[500] * 12, ville='Casablanca',
            jour_reference=datetime.date(2027, 1, 15))
        mensuel, formes, _s = _sources('Casablanca')
        attendu = production_jours_types(10.0, productible_mensuel=mensuel, formes_saison=formes,
                                         derate=PRODUCTION_DERATE)
        self.assertEqual([j['prod_24h'] for j in jours], [m['prod_24h'] for m in attendu])


class TestPurete(unittest.TestCase):

    def test_aucun_import_django(self):
        with open(module_production.__file__, encoding='utf-8') as fh:
            arbre = ast.parse(fh.read())
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                module = noeud.module or ''
            elif isinstance(noeud, ast.Import):
                module = noeud.names[0].name
            else:
                continue
            self.assertNotIn(module.split('.')[0], ('django', 'rest_framework', 'celery'))
            self.assertNotIn('models', module)
            if module.startswith('apps.'):
                self.assertIn(module, ('apps.parametres.pvgis_profils',))
        self.assertTrue(os.path.exists(module_production.__file__))


if __name__ == '__main__':
    unittest.main()
