# -*- coding: utf-8 -*-
"""ACAL392 — l'état du parcours guidé : étapes et « ce qui manque » regroupé.

Tests PURS (ni base, ni réseau) sur les deux fonctions pures du service ;
la forme est comparée au contrat ``calepinage_parcours_guide.json`` (ACAL386).

Run :
    python manage.py test apps.calepinage.tests.test_parcours_guide_service
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.parcours_guide import (
    ETAPES, _etapes_du_parcours, regrouper_manque,
)

CONTRAT = json.loads((pathlib.Path(__file__).resolve().parents[1]
                      / 'contract_samples'
                      / 'calepinage_parcours_guide.json')
                     .read_text(encoding='utf-8'))

NORME = ("aucune norme électrique sélectionnée : les calculs qui en "
         "dépendent sont OMIS")


def _etats(**faits):
    base = dict(toit_fait=True, modules=10, verdict='indetermine',
                simule=False, perime=False, devis_lie=False)
    base.update(faits)
    return {e['cle']: e['etat'] for e in _etapes_du_parcours(**base)}


class ManqueRegroupeTest(unittest.TestCase):
    def test_norme_absente_trois_fois_donne_une_ligne_nombre_3(self):
        lignes = regrouper_manque([NORME, NORME, NORME])
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['code'], 'norme_absente')
        self.assertEqual(lignes[0]['nombre'], 3)
        self.assertEqual(lignes[0]['cible']['onglet'], 'reglages')

    def test_motif_inconnu_garde_tel_quel(self):
        lignes = regrouper_manque(['quelque chose de neuf'])
        self.assertEqual(lignes, [{
            'code': 'divers', 'message': 'quelque chose de neuf',
            'etape': 'resultats', 'cible': {'onglet': 'production',
                                            'champ': ''},
            'gravite': 'info', 'nombre': 1}])

    def test_rien_ne_se_perd(self):
        brut = [NORME, 'simulation périmée : le document a changé',
                'autre', NORME, 'autre']
        lignes = regrouper_manque(brut)
        self.assertEqual(sum(ligne['nombre'] for ligne in lignes), len(brut))

    def test_vide(self):
        self.assertEqual(regrouper_manque(None), [])
        self.assertEqual(regrouper_manque(['', None]), [])

    def test_forme_des_lignes_egale_celle_du_contrat(self):
        modele = CONTRAT['exemple']['manque'][0]
        ligne = regrouper_manque([NORME])[0]
        self.assertEqual(sorted(ligne), sorted(modele))
        self.assertEqual(sorted(ligne['cible']), sorted(modele['cible']))
        self.assertIn(ligne['gravite'], ('bloquant', 'a_regler', 'info'))
        self.assertIn(ligne['etape'], ETAPES)


class EtapesTest(unittest.TestCase):
    def test_calepinage_neuf_tout_a_faire(self):
        etats = _etats(toit_fait=False, modules=0)
        self.assertEqual(set(etats.values()), {'a_faire'})
        attendu = [e['cle'] for e in CONTRAT['exemple_vide']['etapes']]
        self.assertEqual(list(etats), attendu)

    def test_ordre_et_cles_du_contrat(self):
        etapes = _etapes_du_parcours(toit_fait=True, modules=1,
                                     verdict='conforme', simule=True,
                                     perime=False, devis_lie=True)
        self.assertEqual([e['cle'] for e in etapes],
                         [e['cle'] for e in CONTRAT['exemple']['etapes']])

    def test_perime_donne_resultats_en_cours(self):
        self.assertEqual(_etats(simule=True, perime=True)['resultats'],
                         'en_cours')

    def test_verdict_bloquant_bloque_l_electrique(self):
        self.assertEqual(_etats(verdict='bloquant')['electrique'], 'bloque')

    def test_verdicts_conforme_alerte_indetermine(self):
        self.assertEqual(_etats(verdict='conforme')['electrique'], 'fait')
        self.assertEqual(_etats(verdict='alerte')['electrique'], 'fait')
        self.assertEqual(_etats(verdict='indetermine')['electrique'],
                         'en_cours')

    def test_sans_panneaux_electrique_a_faire(self):
        etats = _etats(modules=0, verdict='bloquant')
        self.assertEqual(etats['panneaux'], 'a_faire')
        self.assertEqual(etats['electrique'], 'a_faire')

    def test_documents(self):
        self.assertEqual(_etats(devis_lie=True)['documents'], 'fait')
        self.assertEqual(_etats(simule=True)['documents'], 'en_cours')
        self.assertEqual(_etats()['documents'], 'a_faire')


if __name__ == '__main__':
    unittest.main()
