"""AMOT43 (C-AMOT-054) — le document agricole lit la provenance RÉELLE du
point d'eau : ``provenance_pompage['entrees']`` (forme du producteur
``domain.pompage.derivees_de_l_etude``), ``_empreinte`` ignorée, HMT saisie
(``hmt_saisie_m``) lue sous ``hmt_m``, liste blanche d'affichage (point d'eau,
volume, énergie).

Test PRODUCTEUR → CONSOMMATEUR : la sortie de ``derivees_de_l_etude`` est
passée TELLE QUELLE à ``synthese_agricole`` (aucune provenance écrite à la
main côté consommateur). Rejoue VC agr2 (``provenance_pompage keys
['entrees', '_empreinte']``, ``synthese.provenance {}``, 5 entrées « à
confirmer » dont les mesurées).

Test-du-test : remettre ``etude.get("provenance_pompage").items()`` dans
``_bloc_provenance`` ⇒ ``test_provenance_reelle`` rougit (provenance vide,
mesurées « à confirmer »).
"""
from django.test import SimpleTestCase

from apps.ventes.domain.pompage import derivees_de_l_etude
from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.quote_engine.agricole.synthese import (
    PROVENANCE_AFFICHEE, synthese_agricole)
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete

MESURE = {'origine': 'lead', 'detail': 'mesure_visite', 'date': '2026-09-15'}
FOREUR = {'origine': 'saisie', 'detail': 'foreur', 'date': '2026-09-15'}
CLIENT = {'origine': 'lead', 'detail': 'client', 'date': '2026-09-12'}


def _sortie_moteur():
    """Une sortie ``etudier_pompage`` (forme du contrat
    ``etude_pompage_preview.json``) réduite aux entrées résolues."""
    return {
        'entrees_resolues': {
            'volume_m3_jour': {'valeur': 135, 'provenance': dict(CLIENT)},
            'niveau_statique_m': {'valeur': 30, 'provenance': dict(MESURE)},
            'niveau_dynamique_m': {'valeur': 40, 'provenance': dict(MESURE)},
            'debit_exploitation_m3h': {'valeur': 36,
                                       'provenance': dict(FOREUR)},
            'profondeur_forage_m': {'valeur': 80, 'provenance': dict(MESURE)},
            'hmt_saisie_m': {'valeur': 58.7, 'provenance': dict(MESURE)},
            'cultures': {'valeur': [{'crop': 'olivier', 'ha': 3}],
                         'provenance': dict(CLIENT)},
            'region': {'valeur': 'marrakech_safi',
                       'provenance': dict(CLIENT)},
        },
    }


def _data():
    d = data_complete()
    derivees = derivees_de_l_etude(_sortie_moteur())
    derivees['provenance_pompage']['_empreinte'] = 'empreinte-amot43'
    d['etude']['provenance_pompage'] = derivees['provenance_pompage']
    return d


class ProvenanceReelleTests(SimpleTestCase):

    def test_forme_du_producteur(self):
        prov = _data()['etude']['provenance_pompage']
        self.assertEqual(set(prov), {'entrees', '_empreinte'})

    def test_provenance_reelle(self):
        s = synthese_agricole(_data())
        self.assertEqual(s['provenance']['niveau_statique_m'], MESURE)
        self.assertEqual(s['provenance']['debit_exploitation_m3h'], FOREUR)
        self.assertEqual(s['provenance']['hmt_m'], MESURE)
        self.assertEqual(s['provenance']['volume_m3_jour'], CLIENT)
        # Liste blanche : aucune entrée hors affichage (pas de débordement).
        self.assertTrue(set(s['provenance']) <= set(PROVENANCE_AFFICHEE))
        self.assertNotIn('_empreinte', s['provenance'])
        self.assertNotIn('cultures', s['provenance'])
        # Les mesurées ne sont plus « à confirmer par la visite ».
        self.assertEqual(s['a_confirmer_par_visite'], [])

    def test_annexe_fda_dit_mesure_par(self):
        d = _data()
        d['include_note_calcul'] = True
        d['references_pompage'] = []
        html = pages.build_html(renderer._augment(d))
        self.assertIn('mesuré par Soleil Agri le 15/09/2026', html)

    def test_page1_bloc_borne(self):
        html = pages.build_html(renderer._augment(_data()))
        self.assertNotIn('empreinte', html.lower())
        self.assertNotIn('marrakech_safi', html)
