"""CAL193 — les trois dossiers français (DP mairie, Enedis, Consuel).

Le « Done » : « les trois dossiers se génèrent avec leurs pièces et un état
d'avancement par pièce ; aucune donnée réglementaire chiffrée n'est écrite en
dur (test) ».

Ce qui est vérifié ici, sans base :

* l'avancement se COMPTE sur les pièces réellement fournies, et le
  pourcentage vaut ``None`` quand le dossier n'attend aucune pièce (un
  pourcentage sur zéro pièce serait un chiffre inventé) ;
* un genre dont la société n'a déposé aucun gabarit sort avec son message FR
  disant quoi déposer — ni masqué, ni inventé ;
* TEST DE SURFACE : ``services/reglementaire.py`` ne contient AUCUN littéral
  numérique réglementaire (ni numéro de CERFA, ni seuil de puissance, ni
  délai) — la seule liste écrite en dur est celle des trois CLÉS de genre.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from apps.calepinage.services.reglementaire import (
    ETAT_A_COMPLETER,
    ETAT_FOURNIE,
    ETAT_MANQUANTE,
    GENRES_FRANCE,
    MESSAGE_GENRE_SANS_GABARIT,
    avancement_du_dossier,
    composer_dossiers,
)

#: Les nombres de FORME admis dans le service : ``0``/``1`` sont des bornes,
#: ``100`` la conversion en pourcentage, ``12`` la longueur de l'empreinte
#: tronquée de l'ancre d'idempotence. Aucun n'est une donnée réglementaire.
NOMBRES_DE_FORME = (0, 1, 100, 12)


def _dossier(pieces):
    entree = {
        'id': 1, 'gabarit_id': 1, 'intitule': 'Dossier FR',
        'gabarit': {'id': 1, 'present': True, 'fichier': 'g.pdf',
                    'depose_le': None, 'depose_par': None, 'version': None},
        'pieces_attendues': pieces,
        'champs': [],
        'champs_saisis': {},
        'pieces_jointes': {'plan_situation': {'fichier': 'ps.pdf',
                                              'fichier_url': None}},
        'genere_le': None,
    }
    return composer_dossiers(calepinage_id=1, pays='fr', entrees=[entree],
                             infos={})['dossiers'][0]


PIECES = [
    {'code': 'plan_situation', 'intitule': 'Plan de situation',
     'obligatoire': True, 'source_reference': 'Référence saisie société'},
    {'code': 'plan_masse', 'intitule': 'Plan de masse', 'obligatoire': True,
     'source_reference': 'Référence saisie société'},
    {'code': 'photos', 'intitule': 'Photos', 'obligatoire': False,
     'source_reference': 'Référence saisie société'},
]


class AvancementTest(unittest.TestCase):

    def test_compte_les_pieces_reellement_fournies(self):
        dossier = _dossier([dict(p) for p in PIECES])
        etats = {p['code']: p['etat'] for p in dossier['pieces']}
        self.assertEqual(etats['plan_situation'], ETAT_FOURNIE)
        self.assertEqual(etats['plan_masse'], ETAT_A_COMPLETER)
        self.assertEqual(etats['photos'], ETAT_MANQUANTE)

        avancement = avancement_du_dossier(dossier)
        self.assertEqual(avancement['pieces_total'], 3)
        self.assertEqual(avancement['pieces_fournies'], 1)
        self.assertEqual(avancement['pieces_a_completer'], 1)
        self.assertEqual(avancement['pieces_manquantes'], 1)
        self.assertEqual(avancement['pourcentage'], 33)

    def test_aucune_piece_attendue_aucun_pourcentage(self):
        dossier = _dossier([])
        self.assertIsNone(avancement_du_dossier(dossier)['pourcentage'])


class GenresFranceTest(unittest.TestCase):

    def test_les_trois_genres_sont_declares(self):
        self.assertEqual([genre for genre, _libelle in GENRES_FRANCE],
                         ['dp_mairie', 'enedis', 'consuel'])

    def test_message_quand_aucun_gabarit_n_est_depose(self):
        message = MESSAGE_GENRE_SANS_GABARIT % 'Raccordement Enedis'
        self.assertIn('Raccordement Enedis', message)
        self.assertIn('déposez le formulaire officiel', message.lower())
        self.assertIn('de mémoire', message)


class AucuneDonneeReglementaireEnDurTest(unittest.TestCase):
    """Test de SURFACE : aucun chiffre réglementaire dans le service."""

    def test_aucun_litteral_numerique_hors_formes(self):
        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'services' / 'reglementaire.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        intrus = [
            (noeud.lineno, noeud.value) for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, (int, float))
            and not isinstance(noeud.value, bool)
            and noeud.value not in NOMBRES_DE_FORME
        ]
        self.assertEqual(
            intrus, [],
            "Chiffre écrit en dur dans services/reglementaire.py : une "
            "donnée réglementaire (numéro de CERFA, seuil, délai) se SAISIT "
            "avec sa source sur le gabarit de la société (CAL193).")

    def test_aucun_numero_de_cerfa_ecrit_en_dur(self):
        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'services' / 'reglementaire.py')
        source = chemin.read_text(encoding='utf-8').lower()
        # Le mot « cerfa » n'apparaît qu'en COMMENTAIRE/message, jamais suivi
        # d'un numéro : le numéro vit sur le gabarit déposé par la société.
        for morceau in source.split('cerfa')[1:]:
            self.assertFalse(morceau.lstrip(' :n°*').startswith(
                tuple('0123456789')), 'Un numéro de CERFA est écrit en dur.')
