"""AMOT43 (C-AMOT-054) — le document agricole lit la provenance RÉELLE du
point d'eau (``provenance_pompage['entrees']``, ``_empreinte`` ignorée,
``hmt_saisie_m``) avec une liste blanche d'affichage : une mesure de visite
s'imprime « mesuré par <société> le <date> », seules les entrées non mesurées
restent « à confirmer ».

Test PRODUCTEUR → CONSOMMATEUR : la sortie de
``domain.pompage.derivees_de_l_etude`` passée TELLE QUELLE à
``synthese_agricole`` (aucune fixture écrite à la main). Test-du-test :
remettre ``etude.get("provenance_pompage").items()`` ⇒
``test_mesures_lues_et_plus_a_confirmer`` échoue (provenance vide).
"""
from django.test import SimpleTestCase

from apps.ventes.domain.pompage import _provenance, derivees_de_l_etude
from apps.ventes.quote_engine.agricole import pages
from apps.ventes.quote_engine.agricole.synthese import (
    LISTE_BLANCHE_PROVENANCE, synthese_agricole,
)

_VISITE = _provenance('lead', 'mesure_visite', '2026-09-15')
_FOREUR = _provenance('saisie', 'foreur', '2026-09-16')
_CLIENT = _provenance('lead', 'client', '2026-09-12')


def _sortie_producteur():
    return {
        'entrees_resolues': {
            'niveau_statique_m': {'valeur': 30, 'provenance': _VISITE},
            'niveau_dynamique_m': {'valeur': 38, 'provenance': _VISITE},
            'debit_exploitation_m3h': {'valeur': 36, 'provenance': _FOREUR},
            'profondeur_forage_m': {'valeur': 80, 'provenance': _CLIENT},
            'volume_m3_jour': {'valeur': 135, 'provenance': _CLIENT},
            'hmt_saisie_m': {'valeur': 58.7, 'provenance': _VISITE},
            'cultures': {'valeur': [{'crop': 'olivier', 'ha': 3}],
                         'provenance': _CLIENT},
            'region': {'valeur': 'marrakech_safi', 'provenance': _CLIENT},
        },
        'hmt': {'valeur_m': 58.7},
    }


class ProvenanceReelleTests(SimpleTestCase):
    def _data(self):
        etude = derivees_de_l_etude(_sortie_producteur())
        etude['provenance_pompage']['_empreinte'] = 'empreinte-reelle'
        return {'mode_installation': 'agricole', 'etude': etude,
                'all_items': [], 'langue_sortie': 'fr'}

    def test_mesures_lues_et_plus_a_confirmer(self):
        s = synthese_agricole(self._data())
        prov = s['provenance']
        self.assertEqual(prov['niveau_statique_m']['detail'], 'mesure_visite')
        self.assertEqual(prov['debit_exploitation_m3h']['detail'], 'foreur')
        self.assertEqual(prov['hmt_m']['detail'], 'mesure_visite')
        self.assertNotIn('niveau_statique_m', s['a_confirmer_par_visite'])
        self.assertNotIn('niveau_dynamique_m', s['a_confirmer_par_visite'])
        self.assertNotIn('debit_exploitation_m3h', s['a_confirmer_par_visite'])
        self.assertNotIn('hmt_m', s['a_confirmer_par_visite'])
        # Le forage seulement déclaré reste à confirmer.
        self.assertIn('profondeur_forage_m', s['a_confirmer_par_visite'])

    def test_liste_blanche(self):
        prov = synthese_agricole(self._data())['provenance']
        self.assertTrue(set(prov) <= set(LISTE_BLANCHE_PROVENANCE))
        self.assertNotIn('cultures', prov)
        self.assertNotIn('_empreinte', prov)
        self.assertNotIn('entrees', prov)

    def test_annexe_hmt_mesuree(self):
        data = self._data()
        s = synthese_agricole(data)
        html = pages._hmt_annexe(data, s, 'fr', 'Soleil Agri')
        self.assertIn('mesuré par Soleil Agri', html)
