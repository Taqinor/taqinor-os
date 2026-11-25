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

    def test_textes_servis_en_phrases_simples_et_toujours_ranges(self):
        """ACAL1338 — les phrases SERVIES (constantes des services) ne portent ni sigle
        de norme ni terme de bureau d'études, et chacune garde son code et sa cible."""
        from apps.calepinage.services import electrique, ombrage_chaines
        from apps.calepinage.services.norme import norme_applicable

        sans_norme = norme_applicable({'imagerie': {'pays': 'ma'}, 'norme_electrique': {}})
        production = ("La production n'est pas encore calculée : lancez la simulation "
                      "à l'étape Résultats pour connaître ce que l'installation produira.")
        attendus = {sans_norme['motif']: ('norme_absente', 'reglages'),
                    production: ('production_non_simulee', 'production'),
                    electrique.MENTION_NON_SOURCEE: ('coefficients_non_sources', 'reglages'),
                    ombrage_chaines.MOTIF_SANS_ACCES: ('acces_solaire_absent', 'production')}
        for message, (code, onglet) in attendus.items():
            for jargon in ('OMIS', 'NF C 15-100', 'UTE C 15-712-1', 'silence est explicite',
                           'non sourcées', 'TSRF', 'TOF'):
                self.assertNotIn(jargon, message)
            ligne, = regrouper_manque([message])
            self.assertEqual((ligne['code'], ligne['cible']['onglet']), (code, onglet), message)
        self.assertIn('Choisissez une norme dans les réglages', sans_norme['motif'])

    def test_le_rail_compte_les_memes_lignes_que_la_pastille(self):
        """ACAL1539 — l'étape Électrique du rail compte les contrôles à
        régler de « Prêt à envoyer ? » (mutant : compter les motifs ⇒ échec)."""
        def controle(code, etat, onglet='schema'):
            return {'code': code, 'libelle': code, 'etat': etat,
                    'valeur_texte': 'v', 'cause': 'c', 'geste': '',
                    'cible': {'etape': 'electrique', 'onglet': onglet,
                              'champ': ''}, 'seuil_source': None}
        controles = [controle('verdict_electrique', 'a_regler',
                              'verdict-electrique'),
                     controle('chutes_tension', 'a_regler',
                              'cheminement-cables'),
                     controle('tension_froid', 'bloquant'),
                     controle('ratio_dc_ac', 'info'),
                     controle('materiel_designe', 'ok', 'materiel')]
        brut = [NORME, NORME, 'ratio DC/AC de 1,42 au-dessus de la borne',
                'longueur de chaîne hors plage',
                'simulation périmée : le document a changé']
        lignes = regrouper_manque(brut, controles_electriques=controles)
        pastille = sum(c['etat'] in ('bloquant', 'a_regler')
                       for c in controles)
        rail = sum(ligne['nombre'] for ligne in lignes
                   if ligne['etape'] == 'electrique'
                   and ligne['gravite'] != 'info')
        self.assertEqual(rail, pastille)
        self.assertEqual(rail, 3)
        tension, = [ligne for ligne in lignes
                    if ligne['code'] == 'tension_froid']
        self.assertEqual(tension['gravite'], 'bloquant')
        modele = CONTRAT['exemple']['manque'][0]
        self.assertEqual(sorted(tension), sorted(modele))
        # Les autres étapes gardent leurs avertissements regroupés.
        self.assertIn('simulation_perimee', [ligne['code'] for ligne in lignes])

    def test_obstacles_poses_sans_ombre_enregistree_ne_disent_pas_aucune_ombre(self):
        """T4-U1-023 — toit à cheminée de 1,5 m et bâtiment voisin de 6 m, aucune
        lecture d'ombre enregistrée : la ligne servie NOMME les objets qui portent
        une ombre et le geste, jamais « acces_solaire_absent » (que l'écran lit
        « Aucune ombre n'est signalée »). Sans objet haut, la ligne reste celle d'avant."""
        from apps.calepinage.services.ombrage_chaines import MOTIF_SANS_ACCES

        layout = {'version': 2, 'zones': [
            {'id': 'sud', 'label': 'Pan sud', 'obstacles': [
                {'id': 'o1', 'type': 'cheminee', 'lengthM': 0.8, 'widthM': 0.8,
                 'heightM': 1.5},
                {'id': 'o2', 'type': 'antenne'}]},
            {'id': 'nord', 'label': 'Pan nord', 'obstacles': []}],
            'environment': [{'id': 'b1', 'kind': 'batiment', 'heightM': 6.0,
                             'lengthM': 8.0, 'widthM': 5.0}]}
        ligne, = regrouper_manque([MOTIF_SANS_ACCES], layout=layout)
        self.assertEqual(ligne['code'], 'ombres_non_mesurees')
        self.assertEqual(ligne['gravite'], 'a_regler')
        self.assertEqual(ligne['etape'], 'resultats')
        self.assertEqual(ligne['message'],
                         'Ce toit porte 1 obstacle et 1 objet voisin qui font de '
                         'l’ombre, mais cette ombre n’est pas encore comptée sur les '
                         'panneaux posés : ouvrez le calcul des ombres du toit, puis '
                         'enregistrez et relancez la simulation.')
        self.assertNotIn('Aucune ombre', ligne['message'])
        plat = {'version': 2, 'zones': [{'id': 'sud', 'obstacles': [
            {'id': 'o2', 'type': 'antenne'}]}]}
        ligne, = regrouper_manque([MOTIF_SANS_ACCES], layout=plat)
        self.assertEqual(ligne['code'], 'acces_solaire_absent')
        ligne, = regrouper_manque([MOTIF_SANS_ACCES])
        self.assertEqual(ligne['code'], 'acces_solaire_absent')

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
