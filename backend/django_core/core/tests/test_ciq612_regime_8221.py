# -*- coding: utf-8 -*-
"""CIQ612 — un seul calcul du régime 82-21, sourcé (noyau pur ``core``).

Noyau pur : ``unittest``, aucune base. La sortie suit la forme ``regime`` du
contrat partagé ``apps/ventes/contract_samples/dossier_8221.json`` (CIQ12).
"""
import json
import os
import unittest

from core.reglementaire import regime_8221 as r

_CONTRAT = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, 'apps', 'ventes',
    'contract_samples', 'dossier_8221.json')


def _code(*args, **kwargs):
    return r.regime_8221(*args, **kwargs)['code']


class SeuilsTest(unittest.TestCase):
    def test_constantes_sourcees(self):
        self.assertEqual(r.SEUIL_DECLARATION_KW, 11)
        self.assertEqual(r.SEUIL_AUTORISATION_KW, 5000)
        self.assertIn('décret 2.25.100 art. 5', r.SEUIL_DECLARATION_SOURCE)
        self.assertIn('09/06/2026', r.SEUIL_DECLARATION_SOURCE)
        self.assertIn('art. 5, 18', r.SEUIL_AUTORISATION_SOURCE)

    def test_10_9_kw_declaration(self):
        self.assertEqual(_code(10.9), 'declaration_bt')

    def test_11_kw_accord(self):
        self.assertEqual(_code(11), 'accord_raccordement')

    def test_4999_kw_accord(self):
        self.assertEqual(_code(4999), 'accord_raccordement')

    def test_5000_kw_autorisation(self):
        res = r.regime_8221(5000)
        self.assertEqual(res['code'], 'autorisation_anre')  # valeur stockée
        self.assertEqual(res['libelle'], 'Autorisation')
        self.assertEqual(res['guichet'], 'services_deconcentres_energie')
        self.assertNotIn('ANRE', res['libelle'])

    def test_max_dc_ac(self):
        res = r.regime_8221(12, 10)
        self.assertEqual(res['code'], 'accord_raccordement')
        self.assertEqual(res['puissance_retenue_kw'], 12)
        self.assertEqual(res['base_puissance'],
                         'a_confirmer_avec_le_distributeur')
        self.assertEqual(r.regime_8221(9, 12)['puissance_retenue_kw'], 12)

    def test_puissance_inconnue_a_qualifier(self):
        res = r.regime_8221(None, None)
        self.assertTrue(res['a_qualifier'])
        self.assertIsNone(res['code'])
        self.assertNotEqual(res['code'], 'non_concerne')
        self.assertTrue(r.regime_8221('abc')['a_qualifier'])
        self.assertTrue(r.regime_8221(0)['a_qualifier'])

    def test_hors_reseau_50_kw_declaration_art3(self):
        res = r.regime_8221(50, hors_reseau=True)
        self.assertEqual(res['code'], 'declaration_hors_reseau')
        self.assertEqual(res['base'], 'loi 82-21 art. 3')
        self.assertFalse(res['a_qualifier'])

    def test_site_mt_sous_11_kw_a_qualifier(self):
        self.assertTrue(r.regime_8221(8, niveau='MT')['a_qualifier'])
        self.assertEqual(_code(8, niveau='BT'), 'declaration_bt')

    def test_chaque_resultat_cite_son_article(self):
        for args, kw in (((5,), {}), ((50,), {}), ((6000,), {}),
                         ((50,), {'hors_reseau': True}), ((None,), {})):
            base = r.regime_8221(*args, **kw)['base']
            self.assertRegex(base, r'art\. \d')

    def test_jamais_anre_guichet_et_libelle_sans_seuil(self):
        for p in (5, 50, 6000):
            res = r.regime_8221(p)
            self.assertNotEqual(res['guichet'], 'anre')
            self.assertNotRegex(res['libelle'], r'\d')
            self.assertEqual(res['guichet_statut'], 'a_confirmer')

    def test_surcharges(self):
        self.assertEqual(
            _code(15, surcharges={'seuil_declaration_kw': 20}),
            'declaration_bt')

    def test_alias_suggere(self):
        self.assertEqual(r.regime_8221_suggere(100), 'accord_raccordement')
        self.assertIsNone(r.regime_8221_suggere(None))
        self.assertEqual(r.regime_8221_suggere(100, hors_reseau=True),
                         'declaration_hors_reseau')


class ContratTest(unittest.TestCase):
    def test_forme_conforme_au_contrat_dossier_8221(self):
        with open(_CONTRAT, encoding='utf-8') as fh:
            contrat = json.load(fh)
        attendu = contrat['exemple']['regime']
        res = r.regime_8221(150, 140, niveau='BT')
        self.assertEqual(set(res), set(attendu))
        self.assertEqual(res['code'], attendu['code'])
        self.assertEqual(res['libelle'], attendu['libelle'])
        self.assertEqual(res['base'], attendu['base'])
        self.assertEqual(res['guichet'], attendu['guichet'])
        self.assertEqual(res['puissance_retenue_kw'],
                         attendu['puissance_retenue_kw'])
        mt = r.regime_8221(1200, None, niveau='MT')
        self.assertEqual(set(mt), set(contrat['exemple_mt']['regime']))
        self.assertEqual(mt['puissance_retenue_kw'], 1200)


class PuretéTest(unittest.TestCase):
    def test_aucun_import_d_app(self):
        with open(r.__file__, encoding='utf-8') as fh:
            src = fh.read()
        self.assertNotIn('from apps', src)
        self.assertNotIn('import apps', src)
        self.assertNotIn('django', src)


if __name__ == '__main__':
    unittest.main()
