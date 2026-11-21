"""CAL145 — le comparatif de variantes se joue sur la PRODUCTION.

Ce qui est tenu ici :

* les colonnes de production du contrat (``variantes_comparer.json``) sont
  RÉELLEMENT remplies, depuis la forme imbriquée du module (CAL138/CAL142)
  comme depuis la forme plate du parcours devis ;
* le comparatif est recalculé À LA LECTURE : une conception modifiée depuis la
  dernière simulation rend la variante « non simulée », jamais un chiffre qui
  décrit un autre toit ;
* une variante non simulée porte ``None`` partout — jamais ``0``.

Tests PURS sur le service de lecture : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.comparaison import (
    CLES_PRODUCTION, MOTIF_NON_SIMULEE, MOTIF_PERIMEE, colonnes_production,
)

EMPREINTE = 'a' * 64

#: La forme IMBRIQUÉE que produit le module (CAL138 + CAL142).
RESULTAT_MODULE = {
    'simulation': {'hash_entree': EMPREINTE},
    'production': {
        'total': {'kwc': 8.64, 'p50_kwh': 13000.0, 'p75_kwh': 12400.0,
                  'p90_kwh': 11900.0, 'performance_ratio': 0.8,
                  'specific_yield_kwh_kwc': 1504.6},
    },
    'pertes': [
        {'poste': 'thermique', 'pct': 7.4, 'source': 'fiche'},
        {'poste': 'salissure', 'pct': 3.1, 'source': 'societe'},
        {'poste': 'onduleur', 'pct': 2.5, 'source': 'fiche'},
        {'poste': 'mismatch', 'pct': 2.0, 'source': None},
    ],
    'autoconsommation': {'self_consumption_rate': 0.62},
}

#: La forme PLATE des résultats venus du parcours devis.
RESULTAT_DEVIS = {
    'production': {
        'p50_kwh': 10400.0, 'p75_kwh': 9900.0, 'p90_kwh': 9500.0,
        'performance_ratio': 0.81, 'specific_yield_kwh_kwc': 1444.4,
        'self_consumption': {'self_consumption_rate': 0.66},
        'loss_breakdown': {'temperature': {'pct': 8.0},
                           'soiling': {'pct': 3.0},
                           'inverter': {'pct': 2.5},
                           'mismatch': {'pct': 2.0}},
    },
}


class FormeImbriqueeTest(unittest.TestCase):

    def test_les_colonnes_du_contrat_sont_remplies(self):
        simulee, production, motif = colonnes_production(
            RESULTAT_MODULE)
        self.assertTrue(simulee)
        self.assertEqual(motif, '')
        self.assertEqual(production['p50_kwh'], 13000.0)
        self.assertEqual(production['p90_kwh'], 11900.0)
        self.assertEqual(production['performance_ratio'], 0.8)
        self.assertEqual(production['self_consumption_rate'], 0.62)

    def test_les_pertes_dominantes_sont_les_plus_lourdes_avec_leur_source(self):
        _, production, _ = colonnes_production(RESULTAT_MODULE)
        dominantes = production['pertes_dominantes']
        self.assertEqual([poste['poste'] for poste in dominantes],
                         ['thermique', 'salissure', 'onduleur'])
        self.assertEqual(dominantes[0]['source'], 'fiche')

    def test_un_poste_non_source_reste_non_source(self):
        resultat = dict(RESULTAT_MODULE, pertes=[
            {'poste': 'mismatch', 'pct': 9.0, 'source': None}])
        _, production, _ = colonnes_production(resultat)
        self.assertIsNone(production['pertes_dominantes'][0]['source'])


class FormePlateTest(unittest.TestCase):

    def test_la_forme_du_parcours_devis_est_lue_a_l_identique(self):
        simulee, production, _ = colonnes_production(RESULTAT_DEVIS)
        self.assertTrue(simulee)
        self.assertEqual(production['p50_kwh'], 10400.0)
        self.assertEqual(production['self_consumption_rate'], 0.66)

    def test_le_loss_breakdown_donne_des_postes_SANS_source(self):
        _, production, _ = colonnes_production(RESULTAT_DEVIS)
        dominantes = production['pertes_dominantes']
        self.assertEqual(dominantes[0]['poste'], 'temperature')
        self.assertIsNone(dominantes[0]['source'])
        self.assertEqual(len(dominantes), 3)


class NonSimuleeTest(unittest.TestCase):

    def test_sans_resultat_tout_est_none_et_jamais_zero(self):
        simulee, production, motif = colonnes_production(None)
        self.assertFalse(simulee)
        self.assertEqual(motif, MOTIF_NON_SIMULEE)
        for cle in CLES_PRODUCTION:
            self.assertIsNone(production[cle], cle)
        self.assertEqual(production['pertes_dominantes'], [])

    def test_un_bloc_production_vide_n_est_pas_une_simulation(self):
        simulee, _, motif = colonnes_production(
            {'production': {'total': {'kwc': 8.64}}})
        self.assertFalse(simulee)
        self.assertEqual(motif, MOTIF_NON_SIMULEE)

    def test_une_conception_modifiee_perime_la_production(self):
        simulee, production, motif = colonnes_production(
            RESULTAT_MODULE, perimee=True)
        self.assertFalse(simulee)
        self.assertEqual(motif, MOTIF_PERIMEE)
        self.assertIsNone(production['p50_kwh'])

    def test_rien_n_est_ecrit_dans_le_resultat_lu(self):
        """Le comparatif CALCULE à la lecture : il ne touche pas sa source."""
        avant = repr(RESULTAT_MODULE)
        colonnes_production(RESULTAT_MODULE)
        self.assertEqual(repr(RESULTAT_MODULE), avant)


class ModuleDeLaVarianteTest(unittest.TestCase):
    """ACAL595 — ``lignes[].module`` : le module désigné par les pans."""

    @staticmethod
    def _variante(*modules_des_pans):
        catalogue = {
            'B': {'id': 'produit-2', 'libelle': 'B 430', 'pmaxWc': 430.0,
                  'longueurMm': 2278.0, 'largeurMm': 1134.0},
            'C': {'id': 'produit-3', 'libelle': 'C 600', 'pmaxWc': 600.0,
                  'longueurMm': None, 'largeurMm': 1303.0}}
        zones = []
        for rang, cle in enumerate(modules_des_pans):
            geometrie = {'count': 4}
            if cle:
                geometrie['moduleId'] = catalogue[cle]['id']
            zones.append({'id': f'z{rang}', 'geometry': geometrie})
        from types import SimpleNamespace
        return SimpleNamespace(roof_layout={
            'modules': list(catalogue.values()), 'zones': zones})

    def test_pans_sur_le_meme_module(self):
        from apps.calepinage.selectors import _module_de_la_variante

        self.assertEqual(
            _module_de_la_variante(self._variante('B', 'B')),
            {'id': 'produit-2', 'libelle': 'B 430', 'pmax_wc': 430.0,
             'longueur_mm': 2278.0, 'largeur_mm': 1134.0})

    def test_une_cote_absente_vaut_none(self):
        from apps.calepinage.selectors import _module_de_la_variante

        module = _module_de_la_variante(self._variante('C'))
        self.assertIsNone(module['longueur_mm'])
        self.assertEqual(module['largeur_mm'], 1303.0)

    def test_pans_sur_deux_modules_sont_mixtes(self):
        from apps.calepinage.selectors import _module_de_la_variante

        self.assertEqual(
            _module_de_la_variante(self._variante('B', 'C')), {'mixte': True})
        # même le second pan seul fait basculer : pas de lecture du 1er pan
        self.assertEqual(
            _module_de_la_variante(self._variante('B', None)),
            {'mixte': True})

    def test_aucun_module_designe_donne_none(self):
        from apps.calepinage.selectors import _module_de_la_variante
        from types import SimpleNamespace

        self.assertIsNone(_module_de_la_variante(self._variante(None)))
        self.assertIsNone(_module_de_la_variante(
            SimpleNamespace(roof_layout=None)))


def _resultat_hypotheses(fenetre, poussiere=None, base='PVGIS-SARAH3'):
    reglages = {'fenetre_annees': {'valeur': fenetre, 'source': 'societe'}}
    if poussiere is not None:
        reglages['salissure_mensuelle_pct'] = {
            'valeur': poussiere, 'source': 'societe'}
    return {'simulation': {'reglages_utilises': reglages},
            'meteo': {'base_rayonnement': base, 'mode': 'pluriannuel'}}


class HypothesesComparees(unittest.TestCase):
    """ACAL883 — « mêmes hypothèses » ou la liste des différences servie."""

    def test_reglages_differents_difference_nommee(self):
        import json
        import pathlib

        from apps.calepinage.services.comparaison import hypotheses_comparees

        servi = hypotheses_comparees({
            11: _resultat_hypotheses('2020-2021'),
            12: _resultat_hypotheses('2015-2020')})
        contrat = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'variantes_comparer.json').read_text(encoding='utf-8'))
        self.assertEqual(servi, contrat['exemple']['hypotheses'])
        self.assertFalse(servi['identiques'])

    def test_memes_hypotheses_identiques(self):
        from apps.calepinage.services.comparaison import hypotheses_comparees

        servi = hypotheses_comparees({
            1: _resultat_hypotheses('2020-2021'),
            2: _resultat_hypotheses('2020-2021')})
        self.assertEqual(servi, {'identiques': True, 'comparees': 2,
                                 'differences': []})

    def test_une_cle_absente_d_un_cote_est_non_saisie(self):
        from apps.calepinage.services.comparaison import hypotheses_comparees

        servi = hypotheses_comparees({
            1: _resultat_hypotheses('2020-2021'),
            2: _resultat_hypotheses('2020-2021', poussiere=3.0)})
        (difference,) = servi['differences']
        self.assertEqual(difference['cle'], 'salissure_mensuelle_pct')
        self.assertEqual(difference['valeurs']['1'], 'non saisi')

    def test_la_base_meteo_differente_est_une_difference(self):
        from apps.calepinage.services.comparaison import hypotheses_comparees

        servi = hypotheses_comparees({
            1: _resultat_hypotheses('2020-2021'),
            2: _resultat_hypotheses('2020-2021', base='PVGIS-ERA5')})
        self.assertEqual([d['cle'] for d in servi['differences']],
                         ['meteo.base_rayonnement'])

    def test_une_seule_variante_simulee_donne_null(self):
        from apps.calepinage.services.comparaison import hypotheses_comparees

        self.assertEqual(
            hypotheses_comparees({1: _resultat_hypotheses('2020-2021')}),
            {'identiques': None, 'comparees': 1, 'differences': []})
        self.assertEqual(
            hypotheses_comparees({}),
            {'identiques': None, 'comparees': 0, 'differences': []})


class ConceptionCouranteTest(unittest.TestCase):
    """ACAL978 — la conception courante est comparée d'office, en tête."""

    @staticmethod
    def _comparer(variantes_servies):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage import selectors

        calepinage = SimpleNamespace(
            pk=1, roof_layout=None,
            resultat={'total_modules': 12, 'kwc': 8.64})
        for v in variantes_servies:
            v.calepinage = calepinage
        with mock.patch.object(selectors, 'variantes',
                               return_value=variantes_servies):
            return selectors.comparer_variantes(calepinage)

    @staticmethod
    def _variante(pk, nom, modules, kwc, retenue=False):
        from types import SimpleNamespace

        return SimpleNamespace(
            pk=pk, nom=nom, retenue=retenue, roof_layout=None,
            resultat={'total_modules': modules, 'kwc': kwc})

    def test_une_variante_plus_la_courante_donne_deux_lignes(self):
        servi = self._comparer([self._variante(11, 'B', 14, 10.08)])
        lignes = servi['lignes']
        self.assertEqual(len(lignes), 2)
        courante, variante = lignes
        self.assertIsNone(courante['id'])
        self.assertTrue(courante['courante'])
        self.assertEqual(courante['nom'], 'Conception courante')
        self.assertFalse(courante['est_retenue'])
        self.assertEqual(courante['total_modules'], 12)
        self.assertFalse(variante['courante'])
        # Sans retenue, les écarts se lisent contre la courante.
        self.assertEqual(courante['ecart_modules'], 0)
        self.assertEqual(variante['ecart_modules'], 2)
        self.assertIsNone(servi['retenue_id'])

    def test_avec_une_retenue_les_ecarts_se_lisent_contre_elle(self):
        servi = self._comparer([
            self._variante(11, 'A', 10, 7.2, retenue=True),
            self._variante(12, 'B', 14, 10.08)])
        par_nom = {ligne['nom']: ligne for ligne in servi['lignes']}
        self.assertEqual(servi['lignes'][0]['nom'], 'Conception courante')
        self.assertEqual(servi['retenue_id'], 11)
        self.assertEqual(par_nom['A']['ecart_modules'], 0)
        self.assertEqual(par_nom['Conception courante']['ecart_modules'], 2)
        self.assertEqual(par_nom['B']['ecart_modules'], 4)

    def test_la_lecture_ne_cree_aucune_variante(self):
        from apps.calepinage.selectors import _courante_comme_variante
        from types import SimpleNamespace

        self.assertIsNone(_courante_comme_variante(None))
        self.assertIsNone(_courante_comme_variante(
            SimpleNamespace(pk=None, roof_layout=None, resultat=None)))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
