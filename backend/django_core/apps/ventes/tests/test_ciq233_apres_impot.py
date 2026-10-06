"""CIQ233 — vue INTERNE après impôt d'un industriel, seulement sur le taux
d'IS et l'amortissement DÉCLARÉS par le client ; base amortissable HT quand la
TVA est récupérable.

SimpleTestCase : aucune base.
"""
import copy
import json
import os

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco

_ICI = os.path.dirname(__file__)

TARIF_MT_DECLARE = {
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}}
INVESTISSEMENT = {'ht': 900000.0, 'ttc': 1080000.0}
FISCALITE = {'taux_is_pct': 31, 'amortissement_mode': 'lineaire',
             'duree_ans': 10, 'amortissement_coefficient': None,
             'source': 'déclaré par le comptable du client (test)'}


def _apercu(tva='oui'):
    with open(os.path.join(_ICI, os.pardir, 'contract_samples',
                           'etude_ci_preview.json'), encoding='utf-8') as fh:
        apercu = copy.deepcopy(json.load(fh)['exemple'])
    apercu['entrees_resolues']['tension'] = {'valeur': 'mt'}
    apercu['entrees_resolues']['tva_recuperable'] = {'valeur': tva}
    return apercu


def _bloc(saisies=None, tva='oui', reglages=None):
    return eco.assembler_economie_ci(
        _apercu(tva), tarif_declare=TARIF_MT_DECLARE,
        investissement=INVESTISSEMENT, mode_installation='industriel',
        saisies=saisies or {}, reglages=reglages or {})


def _cles(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _cles(v)
    elif isinstance(o, list):
        for v in o:
            yield from _cles(v)


class ApresImpotTest(SimpleTestCase):
    def test_is_et_lineaire_tva_recuperable_base_ht(self):
        bloc = _bloc({'fiscalite_client': FISCALITE})
        apres = bloc['vue_interne']['apres_impot']
        self.assertEqual(apres['base'], 'ht')
        hyp = {h['cle']: h['valeur'] for h in apres['hypotheses']}
        # Base amortissable = HT de l'option (900 000), pas le TTC.
        self.assertEqual(hyp['base_amortissable_mad'], 900000.0)
        self.assertEqual(hyp['taux_imposition_pct'], 31.0)
        # Linéaire 10 ans : 900 000 / 10 = 90 000 par an.
        self.assertEqual(len(apres['dotations']), 10)
        self.assertAlmostEqual(apres['dotations'][0]['dotation_mad'], 90000.0)
        # Impôt de l'année 1 = (économie − dotation) × 31 % si positif.
        an1 = apres['flux'][1]
        attendu = round(max(0.0, an1['base_imposable_mad']) * 0.31, 2)
        self.assertAlmostEqual(an1['impot_mad'], attendu, places=2)

    def test_tva_non_recuperable_base_ttc(self):
        bloc = _bloc({'fiscalite_client': FISCALITE}, tva='non')
        apres = bloc['vue_interne']['apres_impot']
        hyp = {h['cle']: h['valeur'] for h in apres['hypotheses']}
        self.assertEqual(hyp['base_amortissable_mad'], 1080000.0)

    def test_sans_saisie_omis_meme_si_la_societe_a_ses_reglages(self):
        bloc = _bloc(reglages={'taux_imposition_pct': 31,
                               'amortissement_mode': 'lineaire'})
        self.assertIsNone(bloc['vue_interne']['apres_impot'])
        self.assertEqual(bloc['vue_interne']['apres_impot_motif'],
                         eco.MOTIF_APRES_IMPOT_OMIS)

    def test_aucune_cle_apres_impot_dans_la_publique(self):
        public = eco.economie_ci_publique(
            _bloc({'fiscalite_client': FISCALITE}))
        cles = set(_cles(public))
        self.assertNotIn('apres_impot', cles)
        self.assertNotIn('vue_interne', cles)

    def test_degressif_sans_coefficient_refuse(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            _bloc({'fiscalite_client': dict(
                FISCALITE, amortissement_mode='degressif')})
        self.assertEqual(ctx.exception.champ,
                         'fiscalite_client.amortissement_coefficient')

    def test_sans_source_refuse(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            _bloc({'fiscalite_client': dict(FISCALITE, source='')})
        self.assertEqual(ctx.exception.champ, 'fiscalite_client.source')
