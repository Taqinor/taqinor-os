"""CAD152 — le panneau d'appel ÉCRIT la fiche : il doit savoir COMMENT saisir.

Contrat servi : ``apps/crm/contract_samples/panneau_appel.json`` (CAD147).

Avant CAD152, le contrat servait ``choix: null`` pour un booléen : l'écran
n'avait qu'un champ libre à proposer, où « oui » serait refusé par le serveur
— alors que « l'été est-il différent ? » est la DEUXIÈME question de l'appel
1. Chaque question porte désormais sa ``nature`` (``choix`` / ``nombre`` /
``texte``), lue sur le champ ``crm.Lead`` lui-même, et un booléen est servi
comme le vocabulaire fermé qu'il est (Oui/Non).

Aucune base : l'assemblage des questions ne lit que des attributs d'un
``Lead`` NON ENREGISTRÉ et les métadonnées du modèle.
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.crm import panneau_appel as panneau
from apps.crm.models import Lead

CONTRAT = Path(__file__).resolve().parent / 'contract_samples' / 'panneau_appel.json'


def _questions(**kwargs):
    lead = Lead(nom='Prospect', **kwargs)
    return {q['champ']: q for q in panneau.questions_a_poser(lead)}


class UnBooleenEstUnVocabulaireFerme(SimpleTestCase):
    def test_ete_differente_sert_oui_puis_non(self):
        question = _questions()['ete_differente']
        self.assertEqual(question['nature'], 'choix')
        self.assertEqual(question['choix'], [
            {'valeur': True, 'libelle': 'Oui'},
            {'valeur': False, 'libelle': 'Non'},
        ])

    def test_un_booleen_a_trois_etats_aussi(self):
        """`equip_piscine` (null = pas encore posée) : mêmes deux réponses —
        le « pas encore posée » est l'ABSENCE de réponse, jamais un choix."""
        question = _questions()['equip_piscine']
        self.assertEqual([c['valeur'] for c in question['choix']], [True, False])


class LaNatureEstLueSurLeChamp(SimpleTestCase):
    def test_un_decimal_est_un_nombre_sans_choix(self):
        question = _questions()['facture_hiver']
        self.assertEqual(question['nature'], 'nombre')
        self.assertIsNone(question['choix'])

    def test_un_entier_est_un_nombre(self):
        self.assertEqual(_questions()['nb_personnes_foyer']['nature'], 'nombre')

    def test_un_vocabulaire_ferme_reste_un_choix_dans_l_ordre_du_modele(self):
        question = _questions()['occupation_jour']
        self.assertEqual(question['nature'], 'choix')
        self.assertEqual([c['valeur'] for c in question['choix']],
                         ['present', 'absent', 'partiel'])

    def test_une_chaine_libre_est_un_texte(self):
        self.assertEqual(_questions()['ville']['nature'], 'texte')

    def test_toute_question_servie_porte_une_nature_connue(self):
        for champ, question in _questions().items():
            self.assertIn(question['nature'], ('choix', 'nombre', 'texte'), champ)
            if question['nature'] == 'choix':
                self.assertTrue(question['choix'], champ)
            else:
                self.assertIsNone(question['choix'], champ)


class LaFormeResteCelleDuContrat(SimpleTestCase):
    def test_chaque_question_a_exactement_les_cles_de_l_exemple_committe(self):
        document = json.loads(CONTRAT.read_text(encoding='utf-8'))
        attendues = set(document['exemple']['champs_a_poser'][0])
        self.assertIn('nature', attendues)
        for champ, question in _questions().items():
            self.assertEqual(set(question), attendues, champ)
