"""AGR307 — le bloc « argent » du devis agricole : ``synthese_agricole``
recopie le bloc PUBLIC ``economie_pompage`` (AGR3) tel quel, et l'OMET sinon.

Tests PURS (aucune base) : le bloc d'entrée est l'``exemple`` du contrat
partagé ``economie_pompage.json`` (AGR3), lu sur disque — jamais redéfini ici.
"""
import copy
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole.synthese import (
    CONDITION_ECONOMIES,
    MOTIF_ECONOMIES_ABSENTES,
    MOTIF_ENERGIE_NON_DECLAREE,
    synthese_agricole,
)

_CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'
_INTERDITS = re.compile(r"gratuit|à vie|illimité|coût nul", re.IGNORECASE)


def _bloc_agr3():
    return json.loads((_CONTRATS / 'economie_pompage.json').read_text(
        encoding='utf-8'))['exemple']


def _data(**surcharges):
    data = {
        'mode_installation': 'agricole',
        'etude': {
            'mode_pompe': 'neuve',
            'saisies_economie_pompage': {
                'energie_actuelle': {
                    'valeur': 'butane',
                    'provenance': {'origine': 'saisie', 'detail': None,
                                   'date': '2026-09-12'}}},
        },
        'all_items': [],
        'economie_pompage': _bloc_agr3(),
    }
    data.update(surcharges)
    return data


def _motifs(s):
    return {o['bloc']: o['motif'] for o in s['omissions']}


def _cles(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _cles(v)
    elif isinstance(o, list):
        for v in o:
            yield from _cles(v)


class Agr307EconomiesTests(SimpleTestCase):

    def test_bloc_agr3_present_recopie_champ_a_champ(self):
        bloc = _bloc_agr3()
        attendu = {k: v for k, v in bloc.items() if k != 'vue_interne'}
        s = synthese_agricole(_data())
        self.assertEqual(s['economies'], attendu)
        self.assertNotIn('economies', _motifs(s))

    def test_bloc_absent_cle_absente_et_motif(self):
        data = _data()
        del data['economie_pompage']
        s = synthese_agricole(data)
        self.assertNotIn('economies', s)
        self.assertEqual(_motifs(s)['economies'], MOTIF_ECONOMIES_ABSENTES)

    def test_bloc_non_publiable_omis_avec_ses_motifs(self):
        bloc = _bloc_agr3()
        bloc['publiable_client'] = False
        bloc['motifs_non_publiable'] = ['barème des charges non saisi']
        s = synthese_agricole(_data(economie_pompage=bloc))
        self.assertNotIn('economies', s)
        self.assertEqual(_motifs(s)['economies'],
                         'barème des charges non saisi')

    def test_energie_non_declaree_absente(self):
        data = _data()
        data['etude'] = {'mode_pompe': 'neuve',
                         # le défaut de l'écran n'est jamais une déclaration
                         'current_fuel': 'butane'}
        s = synthese_agricole(data)
        self.assertNotIn('energie_actuelle', s)
        self.assertEqual(_motifs(s)['energie_actuelle'],
                         MOTIF_ENERGIE_NON_DECLAREE)

    def test_energie_declaree_servie_avec_sa_provenance(self):
        s = synthese_agricole(_data())
        self.assertEqual(s['energie_actuelle'], {
            'valeur': 'butane',
            'provenance': {'origine': 'saisie', 'detail': None,
                           'date': '2026-09-12'}})

    def test_aucune_cle_interne_agr3_dans_la_sortie(self):
        bloc = _bloc_agr3()
        bloc['vue_interne'] = {
            'van_mad': 1.0, 'scenario_butane_non_subventionne': {'x': 1},
            'aide_fda_indicative': 9000.0}
        s = synthese_agricole(_data(economie_pompage=bloc))
        cles = set(_cles(s))
        for interdite in ('vue_interne', 'scenario_butane_non_subventionne',
                          'aide_fda_indicative', 'prix_achat'):
            self.assertNotIn(interdite, cles)

    def test_aucun_texte_gratuit_a_vie_illimite(self):
        s = synthese_agricole(_data())
        blob = json.dumps(s, ensure_ascii=False)
        self.assertIsNone(_INTERDITS.search(blob))
        for texte in CONDITION_ECONOMIES.values():
            self.assertIsNone(_INTERDITS.search(texte))

    def test_entree_jamais_mutee(self):
        data = _data()
        avant = copy.deepcopy(data)
        synthese_agricole(data)
        self.assertEqual(data, avant)
