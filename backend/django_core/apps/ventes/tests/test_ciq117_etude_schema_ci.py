"""CIQ117 — clés ``etude_params`` C&I v2 au schéma, propriétaire ``moteur_ci`` ;
le calepinage n'écrit plus d'économies sur un devis commercial/industriel.

SimpleTestCase : aucune base. Les clés viennent du contrat partagé
``contract_samples/etude_ci_preview.json`` (``cles_etude_params_ci_v2``).
"""
import json
import os
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.domain import etude_schema as es
from apps.ventes.domain.etudes import (
    CLES_DERIVEES_NON_COPIEES, etude_params_pour_copie)

_CONTRAT = os.path.join(os.path.dirname(__file__), os.pardir,
                        'contract_samples', 'etude_ci_preview.json')


def _cles_v2():
    with open(_CONTRAT, encoding='utf-8') as fh:
        return json.load(fh)['cles_etude_params_ci_v2']


class SchemaCiV2Test(SimpleTestCase):
    def test_chaque_cle_v2_declaree_avec_son_proprietaire(self):
        cles = _cles_v2()
        for entree in cles['entrees']:
            with self.subTest(cle=entree['cle']):
                regle = es.SCHEMA.get(entree['cle'])
                self.assertIsNotNone(regle)
                self.assertEqual(regle['proprietaire'], entree['proprietaire'])
                self.assertEqual(regle['nature'], es.ENTREE)
        for derivee in cles['derivees']:
            with self.subTest(cle=derivee['cle']):
                regle = es.SCHEMA.get(derivee['cle'])
                self.assertIsNotNone(regle)
                self.assertEqual(regle['proprietaire'], es.MOTEUR_CI)
                self.assertEqual(derivee['proprietaire'], es.MOTEUR_CI)
                self.assertEqual(regle['nature'], es.DERIVEE)

    def test_derivee_etude_ci_ecrite_par_le_navigateur_refusee(self):
        self.assertEqual(
            es.cles_refusees_pour(es.ECRAN, ['etude_ci', 'production_figee']),
            ['etude_ci', 'production_figee'])
        with self.assertRaises(ValueError) as ctx:
            es.fusionner({}, proprietaire=es.ECRAN, etude_ci={'version': 1})
        self.assertIn('etude_ci', str(ctx.exception))
        # Le moteur, lui, a le droit.
        bloc = es.fusionner({}, proprietaire=es.MOTEUR_CI,
                            etude_ci={'version': 1})
        self.assertEqual(bloc['etude_ci'], {'version': 1})

    def test_entrees_ecran_acceptees(self):
        bloc = {
            'mode': 'commercial', 'site': {'ville': 'Marrakech'},
            'tension': 'bt', 'phases': 'tri', 'puissance_souscrite_kva': None,
            'consommation': {'kwh_mensuels': [1] * 12}, 'rythme': {},
            'courbe_mesuree': None, 'toit': {}, 'contraintes': {},
            'options': {}, 'taille_explicite_kwc': 120,
        }
        self.assertEqual(es.valider(bloc), [])
        self.assertEqual(es.cles_refusees_pour(es.ECRAN, bloc), [])

    def test_d_hyb_4_nb_batteries_entree_persistee_dans_options(self):
        """D-HYB-4 (17/11/2026) — ``options.nb_batteries`` est une FEUILLE
        d'entrée : lue dans le corps / le devis, recopiée dans
        ``etude_params.options`` ; une saisie non entière n'est pas un choix."""
        from apps.ventes.domain.etude_ci import FEUILLES, entrees_pour_etude_params
        from apps.ventes.domain.etude_ci_batterie import nb_batteries_choisi
        self.assertIn(('nb_batteries', 'options.nb_batteries'), FEUILLES)
        self.assertEqual(es.valider({'options': {'om': True, 'nb_batteries': 2}}), [])
        self.assertEqual(entrees_pour_etude_params({
            'om': {'valeur': True}, 'nb_batteries': {'valeur': 2}})['options'],
            {'om': True, 'nb_batteries': 2})
        for valeur, attendu in ((2, 2), (2.0, 2), ('3', 3), (1, 1), (0, None), (-1, None),
                                (1.5, None), (True, None), (None, None), ('deux', None),
                                (float('nan'), None), (float('inf'), None)):
            with self.subTest(valeur=valeur):
                self.assertEqual(nb_batteries_choisi(valeur), attendu)

    def test_cle_inconnue_nommee_en_francais(self):
        reproches = es.valider({'cle_inventee_ci': 1})
        self.assertEqual(len(reproches), 1)
        self.assertIn('cle_inventee_ci', reproches[0])
        self.assertIn('Clé inconnue', reproches[0])

    def test_provenance_tva_hors_vocabulaire_refusee_a_l_ecriture(self):
        """ERR-ACC-ETUDE-PARAMS-PROVENANCE — une ``provenance`` inconnue de
        ``tva_recuperable`` est refusée à l'écriture en nommant le champ (elle
        cassait ensuite ``GET …/economie-ci/``) ; les valeurs admises passent."""
        champ = 'saisies_economie_ci.tva_recuperable.provenance'
        with self.assertRaises(ValueError) as ctx:
            es.fusionner({}, proprietaire=es.ECRAN, saisies_economie_ci={
                'tva_recuperable': {'valeur': 'oui', 'provenance': 'devine'}})
        self.assertIn(champ, str(ctx.exception))
        for provenance in ('lead', 'declare_client', None):
            with self.subTest(provenance=provenance):
                self.assertEqual(es.valider({'saisies_economie_ci': {
                    'tva_recuperable': {'valeur': 'non',
                                        'provenance': provenance}}}), [])
        self.assertEqual(es.valider({'saisies_economie_ci': {}}), [])

    def test_cles_v1_retirees_par_ciq129(self):
        """CIQ129 — les clés `a_retirer_v1` ont quitté le schéma : chacune
        reçue est refusée en la nommant."""
        for cle in _cles_v2()['a_retirer_v1']:
            self.assertNotIn(cle, es.SCHEMA)
            self.assertIn(cle, es.CLES_RETIREES_CI_V1)

    def test_derivees_non_copiees(self):
        self.assertIn('etude_ci', CLES_DERIVEES_NON_COPIEES)
        self.assertIn('production_figee', CLES_DERIVEES_NON_COPIEES)
        copie = etude_params_pour_copie({
            'mode': 'industriel', 'etude_ci': {'version': 1},
            'production_figee': {'lat': 1}})
        self.assertEqual(copie, {'mode': 'industriel'})


class LayoutParMarcheTest(SimpleTestCase):
    RESULTAT = {'annualKwh': 180000, 'savings': 240005, 'kwc': 110}

    def test_industriel_mt_aucune_economie_du_layout(self):
        self.assertEqual(es.cles_etude_du_layout('industriel', self.RESULTAT),
                         {})
        self.assertEqual(es.cles_etude_du_layout('commercial', self.RESULTAT),
                         {})

    def test_residentiel_inchange(self):
        self.assertEqual(
            es.cles_etude_du_layout('residentiel', self.RESULTAT),
            {'production_annuelle': 180000, 'economies_annuelles': 240005,
             'production_source': 'calepinage'})  # ACAL101 — provenance
        self.assertEqual(es.cles_etude_du_layout('agricole', {'annualKwh': 5}),
                         {'production_annuelle': 5,
                          'production_source': 'calepinage'})

    def _ecrire(self, mode):
        from apps.ventes.domain import pipeline
        devis = SimpleNamespace(pk=None, etude_params={},
                                mode_installation=mode)
        intention = SimpleNamespace(
            mode_installation=mode, layout={'result': self.RESULTAT},
            composition_les_deux=False)
        with mock.patch.object(pipeline, 'estampiller_provenance',
                               return_value=None), \
                mock.patch.object(pipeline, '_scenario_de',
                                  return_value='Sans batterie'):
            return pipeline.ecrire_etude_params(devis, intention, ())

    def test_pipeline_industriel_n_ecrit_pas_economies(self):
        bloc = self._ecrire('industriel')
        self.assertNotIn('economies_annuelles', bloc)
        self.assertNotIn('production_annuelle', bloc)

    def test_pipeline_residentiel_ecrit_comme_avant(self):
        bloc = self._ecrire('residentiel')
        self.assertEqual(bloc['economies_annuelles'], 240005)
        self.assertEqual(bloc['production_annuelle'], 180000)

    #: ACAL912 — zone 42 modules + champ au sol 176 ; ``result`` racine = le
    #: toit seul (40 424 kWh, rejeu REJEU-NEW-2).
    TOIT_ET_SOL = {
        'panelWatt': 710, 'result': {'annualKwh': 40424, 'savings': 30000},
        'zones': [{'id': 'Z1', 'geometry': {'count': 42}}],
        'poseSurfaces': [{'kind': 'sol', 'id': 'TERRAIN', 'label': 'Champ au sol',
                          'moduleWc': 550, 'engine': {'modules': 176}}]}

    def test_acal912_surface_de_pose_retire_la_production_du_toit_seul(self):
        """Mutant : écrire ``result.annualKwh`` malgré la surface ⇒ rouge."""
        self.assertEqual(
            es.cles_etude_du_layout('residentiel', self.TOIT_ET_SOL['result'], self.TOIT_ET_SOL),
            {'production_annuelle': None, 'production_source': None,
             'economies_annuelles': None})
        devis = SimpleNamespace(pk=None, mode_installation='residentiel', etude_params={
            'production_annuelle': 40424, 'production_source': 'calepinage',
            'economies_annuelles': 30000})
        intention = SimpleNamespace(mode_installation='residentiel', layout=self.TOIT_ET_SOL,
                                    composition_les_deux=False)
        from apps.ventes.domain import pipeline
        with mock.patch.object(pipeline, 'estampiller_provenance', return_value=None), \
                mock.patch.object(pipeline, '_scenario_de', return_value='Sans batterie'):
            bloc = pipeline.ecrire_etude_params(devis, intention, ())
        for cle in ('production_annuelle', 'production_source', 'economies_annuelles'):
            self.assertNotIn(cle, bloc)

    def test_acal912_toit_seul_inchange_au_bit_pres(self):
        toit = {k: v for k, v in self.TOIT_ET_SOL.items() if k != 'poseSurfaces'}
        self.assertEqual(es.cles_etude_du_layout('residentiel', toit['result'], toit),
                         es.cles_etude_du_layout('residentiel', toit['result']))
        vide = dict(self.TOIT_ET_SOL, poseSurfaces=[{'kind': 'sol', 'engine': {'modules': 0}}])
        self.assertEqual(es.cles_etude_du_layout('residentiel', vide['result'], vide)['production_annuelle'],
                         40424)
        self.assertEqual(es.cles_etude_du_layout('industriel', {}, self.TOIT_ET_SOL), {})
