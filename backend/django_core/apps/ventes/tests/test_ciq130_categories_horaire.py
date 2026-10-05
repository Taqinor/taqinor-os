"""CIQ130 — réponses de catégorie commerciale → éléments d'HORAIRE déclarés.

Module pur (aucune base). Les heures sont CIVILES en entrée ; ``courbe_declaree``
rend des jours types en GMT (le Maroc est à GMT depuis le 20/09/2026 :
``decalage_maroc_h`` donne 0 en 2025-2026 pour les mois testés, la lecture
heure-par-heure ci-dessous passe quand même par ce décalage).
"""
import ast
import datetime
import unittest
from pathlib import Path

from apps.parametres.pvgis_profils import decalage_maroc_h
from apps.ventes.moteur_ci.categories import elements_horaire
from apps.ventes.moteur_ci.charge import courbe_declaree

CHEMIN = Path(__file__).resolve().parent.parent / 'moteur_ci' / 'categories.py'
ANNEE = 2025


def _courbe(reponses, categorie, **rythme):
    kwh = rythme.pop('kwh', [6000] * 12)
    base = {'jours_ouverts': [True] * 6 + [False], 'plages': {'ouvre': [[6, 20]]},
            'talon': {'kw': 1}, 'categorie_commerciale': categorie,
            'reponses_categorie': reponses}
    base.update(rythme)
    return courbe_declaree(base, kwh, annee_reference=ANNEE)


def _heure_civile(jour_type, mois, heure):
    decalage = decalage_maroc_h(datetime.date(ANNEE, mois, 15))
    return jour_type['charge_kwh'][(heure - decalage) % 24]


def _ouvre(jours, mois):
    return next(j for j in jours if j['mois'] == mois and j['type_jour'] == 'ouvre')


class CategoriesHoraireTests(unittest.TestCase):

    def test_boulangerie_four_electrique_cuisson_nocturne(self):
        jours, _prov, _al = _courbe({'four': 'electrique', 'cuisson_nocturne': True,
                                     'heures_cuisson': [[2, 6]]}, 'boulangerie')
        jt = _ouvre(jours, 3)
        for h in (2, 3, 4, 5):
            self.assertGreater(_heure_civile(jt, 3, h), 1.0 + 1e-9)
        self.assertAlmostEqual(_heure_civile(jt, 3, 0), 1.0, places=6)

    def test_boulangerie_four_gaz_aucune_plage_nocturne(self):
        jours, _prov, alertes = _courbe({'four': 'gaz', 'cuisson_nocturne': True,
                                         'heures_cuisson': [[2, 6]]}, 'boulangerie')
        jt = _ouvre(jours, 3)
        for h in (2, 3, 4, 5):
            self.assertAlmostEqual(_heure_civile(jt, 3, h), 1.0, places=6)
        self.assertIn('four_gaz', [a['code'] for a in alertes])

    def test_cuisson_nocturne_sans_heures_alerte(self):
        _p, _f, _n, alertes = elements_horaire(
            'boulangerie', {'four': 'electrique', 'cuisson_nocturne': True})
        self.assertIn('heures_cuisson_a_preciser', [a['code'] for a in alertes])

    def test_ecole_fermee_ete_juillet_aout_au_talon(self):
        kwh = [6000] * 6 + [744, 744] + [6000] * 4
        jours, _prov, _al = _courbe({'fermeture_estivale': True, 'fermeture_du': '07-01',
                                     'fermeture_au': '08-31'}, 'ecole', kwh=kwh)
        for mois in (7, 8):
            types = {j['type_jour'] for j in jours if j['mois'] == mois}
            self.assertEqual(types, {'ferme'})
            jt = next(j for j in jours if j['mois'] == mois)
            for valeur in jt['charge_kwh']:
                self.assertAlmostEqual(valeur, 1.0, places=6)

    def test_restaurant_horaires_sans_heures_alerte(self):
        plages, _f, _n, alertes = elements_horaire('restaurant', {'horaires': 'soir'})
        self.assertIsNone(plages)
        self.assertIn('heures_ouverture_a_preciser', [a['code'] for a in alertes])
        plages, _f, _n, _a = elements_horaire('restaurant', {'horaires': 'soir',
                                                             'heures': [[18, 23]]})
        self.assertEqual(plages, {'ouvre': [[18.0, 23.0]]})

    def test_hotel_occupation_sans_effet_et_listee(self):
        a, prov_a, _ = _courbe({'occupation_pct': 70, 'chambres': 40}, 'hotel')
        b, prov_b, _ = _courbe({'occupation_pct': 40, 'chambres': 40}, 'hotel')
        self.assertEqual(a, b)
        self.assertIn('occupation_pct', prov_a['reponses_non_consommees'])
        self.assertIn('chambres', prov_b['reponses_non_consommees'])

    def test_hammam_chauffe_gaz_aucune_charge(self):
        plages, fermetures, _n, alertes = elements_horaire('hammam', {'chauffe': 'gaz'})
        self.assertIsNone(plages)
        self.assertEqual(fermetures, [])
        self.assertIn('chauffe_non_electrique', [a['code'] for a in alertes])


class GardeAstTests(unittest.TestCase):
    def test_module_pur_sans_coefficient(self):
        arbre = ast.parse(CHEMIN.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                self.fail('module pur : aucun import attendu')
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, float) \
                    and 0 < noeud.value < 1:
                self.fail(f'coefficient flottant interdit : {noeud.value}')


if __name__ == '__main__':
    unittest.main()
