"""ACAL871 — le registre des explications et sa GARDE.

Une phrase ne cite QUE des valeurs servies : chaque trou ``{nom}`` est une clé
de ``valeurs``, chaque chemin de ``valeurs`` se résout dans un échantillon de
``contract_samples/``, et le texte, trous retirés, ne montre ni chemin de code
ni identifiant ni chiffre. Tout est lu sur les fichiers : aucune base.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from apps.calepinage.services.explications import (
    FICHIER_EXPLICATIONS, charger_explications,
)

RACINE = Path(__file__).resolve().parents[1]
ECHANTILLONS = RACINE / 'contract_samples'
#: ACAL1742 — l'onglet Économie lit `GET ventes/devis/<pk>/economie/` : son
#: échantillon (contrat de ventes, lu en fichier) fait foi pour ses chemins.
ECHANTILLON_ECONOMIE = RACINE.parent / 'ventes' / 'contract_samples' / 'ventes_economie.json'
ONGLETS = (RACINE.parents[3] / 'frontend' / 'src' / 'features' / 'calepinage'
           / 'atelier' / 'onglets.js')
TROU = re.compile(r'\{([^{}]*)\}')
SELECTEUR = re.compile(r'\[[^\]]+\]')


def _entrees():
    return charger_explications()['entrees']


def _chemins_servis():
    """Tous les chemins ``a.b[].c`` des échantillons (``[]`` = liste)."""
    chemins = set()

    def marcher(noeud, prefixe):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                chemin = f'{prefixe}.{cle}' if prefixe else cle
                chemins.add(chemin)
                marcher(valeur, chemin)
        elif isinstance(noeud, list):
            for element in noeud:
                marcher(element, f'{prefixe}[]')

    for fichier in (*ECHANTILLONS.glob('*.json'), ECHANTILLON_ECONOMIE):
        marcher(json.loads(fichier.read_text(encoding='utf-8')), '')
    return chemins


def _se_resout(chemin, servis):
    cherche = SELECTEUR.sub('[]', chemin)
    return any(c == cherche or c.endswith('.' + cherche) for c in servis)


def _problemes(entrees, servis, onglets):
    """Les défauts du registre, en phrases : liste vide = registre sain."""
    problemes, vues = [], set()
    for e in entrees:
        cle = e.get('cle')
        if cle in vues:
            problemes.append(f'{cle} : clé en double')
        vues.add(cle)
        phrase, valeurs = e.get('phrase', ''), e.get('valeurs') or {}
        for trou in TROU.findall(phrase):
            if trou not in valeurs:
                problemes.append(f'{cle} : le trou {{{trou}}} n\'a pas de valeur')
        for nom, chemin in valeurs.items():
            if not _se_resout(chemin, servis):
                problemes.append(f'{cle} : {nom} → chemin introuvable {chemin}')
        nue = TROU.sub('', phrase)
        if any(m in nue for m in ('::', '[]', '.py')):
            problemes.append(f'{cle} : chemin de code dans la phrase')
        if re.search(r'[a-z]+_[a-z_]+', nue):
            problemes.append(f'{cle} : identifiant dans la phrase')
        if re.search(r'\d', nue) and not e.get('source'):
            problemes.append(f'{cle} : chiffre sans source dans la phrase')
        for ecran in e.get('ecrans') or []:
            if f"cle: '{ecran}'" not in onglets:
                problemes.append(f'{cle} : écran inconnu {ecran}')
    return problemes


class GardeDuRegistreTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.servis = _chemins_servis()
        cls.onglets = ONGLETS.read_text(encoding='utf-8')

    def test_le_registre_livre_est_sain(self):
        self.assertEqual(_problemes(_entrees(), self.servis, self.onglets), [])

    def test_trou_sans_valeur_echoue(self):
        faux = [{'cle': 'x.y', 'famille': 'x', 'phrase': 'Valeur {x}.',
                 'valeurs': {}, 'ecrans': []}]
        self.assertTrue(_problemes(faux, self.servis, self.onglets))

    def test_chemin_inexistant_echoue(self):
        faux = [{'cle': 'x.y', 'famille': 'x', 'phrase': 'Valeur {x}.',
                 'valeurs': {'x': 'production.total.inconnu_nulle_part'},
                 'ecrans': []}]
        self.assertTrue(_problemes(faux, self.servis, self.onglets))

    def test_chemin_de_code_dans_la_phrase_echoue(self):
        faux = [{'cle': 'x.y', 'famille': 'x', 'ecrans': [],
                 'phrase': 'Voir services/norme.py::norme.'}]
        self.assertTrue(_problemes(faux, self.servis, self.onglets))

    def test_chiffre_dans_la_phrase_echoue(self):
        faux = [{'cle': 'x.y', 'famille': 'x', 'phrase': 'Environ 12 kWh.',
                 'ecrans': []}]
        self.assertTrue(_problemes(faux, self.servis, self.onglets))

    def test_cle_en_double_echoue(self):
        une = {'cle': 'x.y', 'famille': 'x', 'phrase': 'Texte.', 'ecrans': []}
        self.assertTrue(_problemes([une, dict(une)], self.servis, self.onglets))

    def test_ecran_inconnu_echoue(self):
        faux = [{'cle': 'x.y', 'famille': 'x', 'phrase': 'Texte.',
                 'ecrans': ['nulle_part']}]
        self.assertTrue(_problemes(faux, self.servis, self.onglets))


class HorizonEconomieTest(unittest.TestCase):
    def test_la_phrase_de_l_horizon_dit_l_horizon_servi(self):
        # ACAL1742 — « écrit ici » ne disait rien : le trou lit `horizon_ans`.
        entree = next(e for e in _entrees() if e['cle'] == 'economie.horizon')
        self.assertIn('{horizon} ans', entree['phrase'])
        self.assertEqual(entree['valeurs'], {'horizon': 'horizon_ans'})
        self.assertNotIn('écrit ici', entree['phrase'])


class ServiTest(unittest.TestCase):

    def test_le_service_rend_le_fichier_trie(self):
        fichier = json.loads(
            FICHIER_EXPLICATIONS.read_text(encoding='utf-8'))['entrees']
        trie = sorted(fichier, key=lambda e: (e['famille'], e['cle']))
        self.assertEqual(charger_explications(), {'entrees': trie})
        self.assertEqual(fichier, trie)

    def test_la_forme_est_celle_du_contrat_et_son_exemple_est_un_extrait(self):
        contrat = json.loads(
            (ECHANTILLONS / 'calepinage_explications.json')
            .read_text(encoding='utf-8'))
        servi = charger_explications()
        self.assertEqual(sorted(servi), sorted(contrat['exemple']))
        for entree in contrat['exemple']['entrees']:
            self.assertIn(entree, servi['entrees'])

    def test_la_porte_est_rattachee_et_lisible_par_qui_voit_le_module(self):
        from apps.calepinage.permissions import PeutVoirCalepinage
        from apps.calepinage.views import rattachements
        from apps.calepinage.views.calepinages import CalepinageViewSet

        self.assertIn('explications', rattachements.MODULES_RATTACHES)
        action = CalepinageViewSet.explications
        self.assertEqual(action.url_path, 'explications')
        self.assertFalse(action.detail)
        self.assertEqual(action.kwargs['permission_classes'],
                         [PeutVoirCalepinage])


if __name__ == '__main__':      # pragma: no cover
    unittest.main()
