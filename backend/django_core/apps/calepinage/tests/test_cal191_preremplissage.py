"""CAL191 — un dossier prérempli ne porte AUCUNE valeur fabriquée.

Le « Done » de la tâche : « un gabarit rendu sur un calepinage incomplet porte
des mentions "à compléter" et zéro valeur fabriquée (test sur un jeu
volontairement lacunaire) ». C'est exactement ce que ce fichier mesure, et il
le mesure SANS BASE : la règle vit dans ``composer_dossiers``, qui ne connaît
que des dictionnaires.

Il vérifie aussi que la forme servie est celle du contrat CAL247
(``contract_samples/dossiers_reglementaires.json``) — clé par clé, sur les
DEUX états publiés (société avec gabarits, société sans aucun gabarit).
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.reglementaire import (
    ETAT_A_COMPLETER,
    ETAT_FOURNIE,
    ETAT_MANQUANTE,
    MESSAGE_AUCUN_GABARIT,
    composer_dossiers,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'dossiers_reglementaires.json').read_text(encoding='utf-8'))

GABARIT_DEPOSE = {
    'id': 1,
    'present': True,
    'fichier': 'gabarit-essai.pdf',
    'depose_le': '2026-09-01T10:00:00Z',
    'depose_par': {'id': 1, 'nom_complet': "Utilisateur d'essai"},
    'version': '1',
}

PIECES = [
    {'code': 'piece-a', 'intitule': 'Pièce A', 'obligatoire': True,
     'source_reference': 'Référence saisie par la société'},
    {'code': 'piece-b', 'intitule': 'Pièce B', 'obligatoire': False,
     'source_reference': 'Référence saisie par la société'},
]

CHAMPS = [
    {'code': 'societe', 'libelle': 'Société', 'type': 'texte',
     'obligatoire': True, 'cle_calepinage': 'societe_nom'},
    {'code': 'puissance', 'libelle': 'Puissance (kWc)', 'type': 'nombre',
     'obligatoire': True, 'cle_calepinage': 'puissance_kwc'},
    {'code': 'reference_dossier', 'libelle': 'Référence du dossier',
     'type': 'texte', 'obligatoire': True},
]


def _entree(**surcharges):
    entree = {
        'id': 1,
        'gabarit_id': 1,
        'intitule': "Dossier d'essai — intitulé porté par le gabarit déposé",
        'gabarit': dict(GABARIT_DEPOSE),
        'pieces_attendues': [dict(p) for p in PIECES],
        'champs': [dict(c) for c in CHAMPS],
        'champs_saisis': {},
        'pieces_jointes': {},
        'genere_le': None,
    }
    entree.update(surcharges)
    return entree


#: Le jeu VOLONTAIREMENT LACUNAIRE : la société est connue, la puissance ne
#: l'est pas, et la référence du dossier n'a aucune source côté serveur.
INFOS_LACUNAIRES = {
    'societe_nom': 'Taqinor SARL',
    'client_nom': None,
    'adresse': None,
    'puissance_kwc': None,
    'nombre_modules': None,
    'orientation_deg': None,
    'inclinaison_deg': None,
}


def _champ(dossier, code):
    return next(c for c in dossier['champs_a_completer'] if c['code'] == code)


class PreremplissageTest(unittest.TestCase):

    def setUp(self):
        self.agregat = composer_dossiers(
            calepinage_id=1, pays='ma', entrees=[_entree()],
            infos=INFOS_LACUNAIRES)
        self.dossier = self.agregat['dossiers'][0]

    def test_valeur_reelle_servie_telle_quelle(self):
        self.assertEqual(_champ(self.dossier, 'societe')['valeur'],
                         'Taqinor SARL')
        self.assertEqual(_champ(self.dossier, 'societe')['message'], '')

    def test_champ_sans_source_marque_a_completer_et_valeur_nulle(self):
        for code in ('puissance', 'reference_dossier'):
            champ = _champ(self.dossier, code)
            self.assertIsNone(champ['valeur'], code)
            self.assertIn("Aucune valeur n'est préremplie", champ['message'])

    def test_zero_valeur_fabriquee(self):
        valeurs = {c['code']: c['valeur']
                   for c in self.dossier['champs_a_completer']}
        # La SEULE valeur servie est celle que le calepinage porte vraiment.
        self.assertEqual({c: v for c, v in valeurs.items() if v is not None},
                         {'societe': 'Taqinor SARL'})

    def test_champ_deja_saisi_n_est_plus_a_completer(self):
        agregat = composer_dossiers(
            calepinage_id=1, pays='ma',
            entrees=[_entree(champs_saisis={'reference_dossier': 'DP-42'})],
            infos=INFOS_LACUNAIRES)
        codes = [c['code']
                 for c in agregat['dossiers'][0]['champs_a_completer']]
        self.assertNotIn('reference_dossier', codes)

    def test_dossier_incomplet_ne_se_genere_pas_et_dit_pourquoi(self):
        self.assertFalse(self.dossier['peut_generer'])
        self.assertIn('Puissance (kWc)', self.dossier['motif_non_generable'])
        self.assertEqual(self.dossier['statut'], 'incomplet')

    def test_dossier_complet_se_genere(self):
        agregat = composer_dossiers(
            calepinage_id=1, pays='ma', entrees=[_entree(
                champs_saisis={'societe': 'Taqinor SARL',
                               'puissance': 12.3,
                               'reference_dossier': 'DP-42'},
                pieces_jointes={'piece-a': {'fichier': 'a.pdf',
                                            'fichier_url': None}},
            )], infos=INFOS_LACUNAIRES)
        dossier = agregat['dossiers'][0]
        self.assertTrue(dossier['peut_generer'])
        self.assertEqual(dossier['statut'], 'complet')
        self.assertEqual(dossier['motif_non_generable'], '')


class PiecesTest(unittest.TestCase):

    def test_etats_des_pieces(self):
        agregat = composer_dossiers(
            calepinage_id=1, pays='ma',
            entrees=[_entree(pieces_jointes={
                'piece-a': {'fichier': 'a.pdf', 'fichier_url': None}})],
            infos=INFOS_LACUNAIRES)
        pieces = {p['code']: p for p in agregat['dossiers'][0]['pieces']}
        self.assertEqual(pieces['piece-a']['etat'], ETAT_FOURNIE)
        self.assertEqual(pieces['piece-b']['etat'], ETAT_MANQUANTE)

    def test_piece_obligatoire_absente_est_a_completer(self):
        agregat = composer_dossiers(
            calepinage_id=1, pays='ma', entrees=[_entree()],
            infos=INFOS_LACUNAIRES)
        pieces = {p['code']: p for p in agregat['dossiers'][0]['pieces']}
        self.assertEqual(pieces['piece-a']['etat'], ETAT_A_COMPLETER)

    def test_chaque_piece_porte_sa_source_et_sa_reference(self):
        agregat = composer_dossiers(
            calepinage_id=1, pays='ma', entrees=[_entree()],
            infos=INFOS_LACUNAIRES)
        for piece in agregat['dossiers'][0]['pieces']:
            self.assertEqual(piece['source']['type'], 'gabarit_societe')
            self.assertEqual(piece['source']['gabarit_id'], 1)
            self.assertTrue(piece['source']['reference'])


class GabaritManquantTest(unittest.TestCase):

    def test_dossier_reste_visible_sans_son_fichier(self):
        agregat = composer_dossiers(
            calepinage_id=1, pays='ma',
            entrees=[_entree(gabarit={'id': 2, 'present': False,
                                      'fichier': None, 'depose_le': None,
                                      'depose_par': None, 'version': None})],
            infos=INFOS_LACUNAIRES)
        dossier = agregat['dossiers'][0]
        self.assertEqual(dossier['statut'], 'gabarit_manquant')
        self.assertEqual(dossier['pieces'], [])
        self.assertEqual(dossier['champs_a_completer'], [])
        self.assertFalse(dossier['peut_generer'])
        self.assertIn("n'a pas été déposé", dossier['motif_non_generable'])

    def test_societe_sans_gabarit_ne_voit_aucun_dossier(self):
        agregat = composer_dossiers(calepinage_id=2, pays='ma', entrees=[],
                                    infos={})
        self.assertEqual(agregat['dossiers'], [])
        self.assertEqual(agregat['gabarits_deposes'], 0)
        self.assertEqual(agregat['message_aucun_gabarit'],
                         MESSAGE_AUCUN_GABARIT)


class ContratCAL247Test(unittest.TestCase):
    """La forme servie est celle du contrat, clé par clé."""

    def test_forme_de_l_agregat(self):
        agregat = composer_dossiers(calepinage_id=1, pays='ma',
                                    entrees=[_entree()],
                                    infos=INFOS_LACUNAIRES)
        self.assertEqual(sorted(agregat), sorted(CONTRAT['exemple']))

    def test_forme_de_l_etat_vide(self):
        agregat = composer_dossiers(calepinage_id=2, pays='ma', entrees=[],
                                    infos={})
        self.assertEqual(sorted(agregat), sorted(CONTRAT['exemple_vide']))

    def test_forme_d_un_dossier_et_de_ses_sous_objets(self):
        agregat = composer_dossiers(calepinage_id=1, pays='ma',
                                    entrees=[_entree()],
                                    infos=INFOS_LACUNAIRES)
        servi = agregat['dossiers'][0]
        attendu = CONTRAT['exemple']['dossiers'][0]
        self.assertEqual(sorted(servi), sorted(attendu))
        self.assertEqual(sorted(servi['gabarit']), sorted(attendu['gabarit']))
        self.assertEqual(sorted(servi['champs_a_completer'][0]),
                         sorted(attendu['champs_a_completer'][0]))
        # La pièce servie porte les clés du contrat ; ``source.reference``
        # s'y AJOUTE (la référence saisie par la société avec sa pièce).
        self.assertEqual(
            sorted(set(attendu['pieces'][0]) - set(servi['pieces'][0])), [])
        self.assertEqual(
            sorted(set(attendu['pieces'][0]['source'])
                   - set(servi['pieces'][0]['source'])), [])

    def test_pays_servi_en_majuscules_comme_le_contrat(self):
        agregat = composer_dossiers(calepinage_id=1, pays='ma', entrees=[],
                                    infos={})
        self.assertEqual(agregat['pays'], CONTRAT['exemple']['pays'])
