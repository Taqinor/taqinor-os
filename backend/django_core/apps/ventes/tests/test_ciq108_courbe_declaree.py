"""CIQ108 — courbe de charge DÉCLARÉE en jours types (unittest pur, sans base)."""

import ast
import json
import os
import unittest

from apps.ventes.moteur_ci import charge
from apps.ventes.moteur_ci.charge import courbe_declaree

LUN_VEN = [True] * 5 + [False] * 2
TOUS = [True] * 7
# 2027 : Maroc à UTC+0 toute l'année (décret 2.26.530) ⇒ heure civile = GMT.
ANNEE = 2027


def _par(jours_types, mois, type_jour):
    return next(j for j in jours_types if j['mois'] == mois and j['type_jour'] == type_jour)


def _energie_mois(jours_types, mois):
    return sum(j['nb_jours'] * sum(j['charge_kwh']) for j in jours_types if j['mois'] == mois)


def _production_cloche():
    """Production de test PAR kWc (forme quelconque, diurne) — fixture, pas une donnée."""
    jour = [0.0] * 6 + [0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.0, 0.9, 0.8, 0.6, 0.4, 0.2] + [0.0] * 6
    return [{'mois': m, 'production_kwh_kwc': list(jour)} for m in range(1, 13)]


class TestCourbeDeclaree(unittest.TestCase):

    def test_bureau_lun_ven_dimanche_talon(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]},
                  'talon': {'kw': 2.0}}
        jt, prov, _al = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE, feries=[])
        self.assertEqual(prov['methode'], 'declare')
        dimanche = _par(jt, 3, 'ferme')
        for valeur in dimanche['charge_kwh']:
            self.assertAlmostEqual(valeur, 2.0)
        ouvre = _par(jt, 3, 'ouvre')
        self.assertAlmostEqual(ouvre['charge_kwh'][3], 2.0)      # nuit = talon
        self.assertGreater(ouvre['charge_kwh'][10], 2.0)          # plage chargée
        self.assertFalse(any(j['type_jour'] in ('samedi', 'dimanche') for j in jt))

    def test_ecole_fermee_ete_talon(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 17]]},
                  'fermetures': [{'du': '2027-07-01', 'au': '2027-08-31', 'motif': 'vacances'}],
                  'talon': {'kw': 1.5}}
        jt, _prov, _al = courbe_declaree(rythme, [4000] * 12, annee_reference=ANNEE, feries=[])
        for mois in (7, 8):
            types = {j['type_jour'] for j in jt if j['mois'] == mois}
            self.assertEqual(types, {'ferme'})
        self.assertIn('ouvre', {j['type_jour'] for j in jt if j['mois'] == 6})

    def test_3x8_continu_quasi_plat(self):
        rythme = {'jours_ouverts': TOUS, 'equipes': '3x8', 'talon': {'kw': 5.0}}
        jt, _prov, _al = courbe_declaree(rythme, [24000] * 12, annee_reference=ANNEE, feries=[])
        for j in jt:
            self.assertLess(max(j['charge_kwh']) - min(j['charge_kwh']), 1e-9)

    def test_somme_mois_egale_kwh_declares(self):
        kwh = [9800, 9200, 10100, 10800, 12500, 14800, 17200, 17600, 14900, 12100, 10200, 9900]
        rythme = {'jours_ouverts': [True] * 6 + [False],
                  'plages': {'ouvre': [[7.5, 19]], 'samedi': [[8, 13]]},
                  'talon': {'part_pct': 20}}
        jt, _prov, _al = courbe_declaree(rythme, kwh, annee_reference=ANNEE,
                                         feries=['2027-01-11', '2027-05-01'])
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt, mois), kwh[mois - 1], delta=1e-6)
        # samedi : ses propres plages ; férié du 11/01 : jour fermé
        self.assertIn('samedi', {j['type_jour'] for j in jt if j['mois'] == 1})
        self.assertEqual(sum(j['nb_jours'] for j in jt if j['mois'] == 1
                             and j['type_jour'] == 'ferme'), 6)   # 5 dimanches + 1 férié

    def test_talon_inconnu_borne_conservatrice_et_alerte(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}}
        production = _production_cloche()
        jt, prov, alertes = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE,
                                            feries=[], production_jours_types=production)
        codes = {a['code'] for a in alertes}
        self.assertIn('talon_non_declare', codes)
        self.assertEqual(prov['talon']['statut'], 'borne_conservatrice')
        # bureau diurne : étaler sur 24 h donne MOINS d'autoconsommation que talon 0
        self.assertEqual(prov['bornes']['retenue'], 'etale_24h')
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt, mois), 10000, delta=1e-6)
        # atelier de nuit : c'est le talon 0 (tout la nuit) qui est conservateur
        nuit = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[20, 6]]}}
        _jt, prov, _al = courbe_declaree(nuit, [10000] * 12, annee_reference=ANNEE,
                                         feries=[], production_jours_types=production)
        self.assertEqual(prov['bornes']['retenue'], 'talon_nul')

    def test_talon_inconnu_sans_production_rien_d_invente(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}}
        jt, _prov, alertes = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE, feries=[])
        self.assertIsNone(jt)
        self.assertIn('production_requise_pour_borne', {a['code'] for a in alertes})

    def test_jours_ouverts_non_declares_jamais_5_sur_7(self):
        rythme = {'plages': {'ouvre': [[8, 18]]}, 'talon': {'kw': 1}}
        jt, _prov, alertes = courbe_declaree(rythme, [1000] * 12, annee_reference=ANNEE, feries=[])
        self.assertIsNone(jt)
        self.assertIn('jours_ouverts_non_declares', {a['code'] for a in alertes})

    def test_archetype_seulement_sans_plage(self):
        jt, prov, alertes = courbe_declaree({}, 42000, annee_reference=ANNEE,
                                            archetype='bureau', feries=None)
        self.assertEqual(prov['methode'], 'archetype')
        self.assertEqual(prov['niveau_donnees'], 'estimation')
        self.assertEqual(prov['archetype']['cle'], 'bureau')
        self.assertEqual(prov['repartition'], 'annuel_prorata')
        total = sum(j['nb_jours'] * sum(j['charge_kwh']) for j in jt)
        self.assertAlmostEqual(total, 42000, delta=1e-6)
        codes = {a['code'] for a in alertes}
        self.assertIn('profil_estime', codes)
        self.assertIn('feries_non_saisis', codes)

    def test_sans_plage_ni_archetype_profil_exige(self):
        jt, _prov, alertes = courbe_declaree({'jours_ouverts': TOUS}, [1000] * 12,
                                             annee_reference=ANNEE, archetype='hammam', feries=[])
        self.assertIsNone(jt)
        self.assertIn('profil_declare_exige', {a['code'] for a in alertes})

    def test_heure_civile_vers_gmt_par_decalage_maroc(self):
        # janvier 2026 : UTC+1 (avant le décret) ⇒ 8 h civile = 7 h GMT
        rythme = {'jours_ouverts': TOUS, 'plages': {'ouvre': [[8, 9]]}, 'talon': {'kw': 0}}
        jt, prov, _al = courbe_declaree(rythme, [31] * 12, annee_reference=2026, feries=[])
        self.assertEqual(prov['heures'], 'GMT')
        janvier = _par(jt, 1, 'ouvre')
        self.assertAlmostEqual(janvier['charge_kwh'][7], 1.0)
        self.assertAlmostEqual(janvier['charge_kwh'][8], 0.0)
        # novembre 2026 : UTC+0 ⇒ 8 h civile = 8 h GMT
        novembre = _par(jt, 11, 'ouvre')
        self.assertGreater(novembre['charge_kwh'][8], 0.0)
        self.assertAlmostEqual(novembre['charge_kwh'][7], 0.0)

    def test_aucune_part_diurne(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}, 'talon': {'kw': 2}}
        sortie = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE, feries=[])
        texte = json.dumps(sortie)
        for interdit in ('part_diurne', 'day_share', 'dayPct'):
            self.assertNotIn(interdit, texte)


class TestPurete(unittest.TestCase):

    def test_aucun_import_django(self):
        with open(charge.__file__, encoding='utf-8') as fh:
            arbre = ast.parse(fh.read())
        modules = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules.extend(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                modules.append(noeud.module or '')
        for module in modules:
            self.assertFalse(module.split('.')[0] in ('django', 'rest_framework', 'celery'), module)
            self.assertNotIn('models', module)
        self.assertTrue(os.path.exists(charge.__file__))


if __name__ == '__main__':
    unittest.main()
