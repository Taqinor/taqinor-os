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

    def test_cle_inconnue_nommee_en_francais(self):
        reproches = es.valider({'cle_inventee_ci': 1})
        self.assertEqual(len(reproches), 1)
        self.assertIn('cle_inventee_ci', reproches[0])
        self.assertIn('Clé inconnue', reproches[0])

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
            {'production_annuelle': 180000, 'economies_annuelles': 240005})
        self.assertEqual(es.cles_etude_du_layout('agricole', {'annualKwh': 5}),
                         {'production_annuelle': 5})

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
