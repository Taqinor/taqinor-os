"""CAL238 — la politique de pertes : ``loss`` est une ENTRÉE, jamais un défaut.

Tests PURS (aucune base, aucun réseau) : la politique n'a pas de dépendance
Django, et c'est voulu — une règle de calcul se teste sans infrastructure.

LE TEST DE SURFACE, ET POURQUOI IL EST CIBLÉ
--------------------------------------------
CAL238 demande qu'« aucun littéral 14/0.14/20/0.2 ne subsiste dans
``apps/calepinage`` ». Pris au pied de la lettre, un balayage aveugle de tous
les chiffres échouerait sur des littéraux qui n'ont RIEN à voir avec les
pertes (``max_iterations=20`` dans ``services/pompage.py``, un ``round(x, 2)``,
une longueur de champ…) : il interdirait le chiffre 20 au lieu d'interdire la
perte cachée. Le balayage ci-dessous vise donc ce que la règle vise vraiment :
un littéral numérique utilisé COMME une perte (ligne parlant de perte/loss,
affectation à un nom de perte, clé ``loss``) et les constantes nommées du site
public qui portent exactement le défaut interdit.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from apps.calepinage.services.pertes_politique import (
    PertesInvalides, politique_de_pertes,
)

#: Un jeu de postes d'ESSAI (repères visiblement factices) : ces tests
#: vérifient la MÉCANIQUE d'addition et de publication, jamais un chiffre de
#: perte réel — les vraies valeurs sont saisies par la société (CAL139).
POSTES_ESSAI = [
    {'poste': 'shading', 'libelle': 'Ombrage', 'pct': 3.5, 'source': 'mesure'},
    {'poste': 'soiling', 'libelle': 'Salissure', 'pct': 2.25,
     'source': 'societe'},
    {'poste': 'inverter', 'libelle': 'Onduleur', 'pct': 1.5,
     'source': 'fiche'},
]


class PolitiqueDePertesTest(unittest.TestCase):
    """La somme est explicite, publiée, et refusée quand elle n'existe pas."""

    def test_somme_explicite_publiee_avec_chaque_source(self):
        politique = politique_de_pertes(POSTES_ESSAI)

        self.assertEqual(politique.valeur_loss, '7.25')
        self.assertEqual(politique.total_pct, 7.25)
        publication = politique.publication()
        self.assertEqual(publication['loss_passee_pct'], 7.25)
        self.assertEqual(
            [(p['poste'], p['pct'], p['source'])
             for p in publication['pertes']],
            [('shading', 3.5, 'mesure'), ('soiling', 2.25, 'societe'),
             ('inverter', 1.5, 'fiche')])

    def test_valeur_loss_et_total_publie_ne_peuvent_pas_diverger(self):
        # La chaîne écrite fait foi : le total publié en est la relecture.
        politique = politique_de_pertes(
            [{'poste': 'a', 'pct': 1.0005, 'source': 'saisie'},
             {'poste': 'b', 'pct': 2.0005, 'source': 'saisie'}])
        self.assertEqual(float(politique.valeur_loss), politique.total_pct)

    def test_aucun_poste_refuse_plutot_que_de_supposer_un_defaut(self):
        with self.assertRaises(PertesInvalides) as capture:
            politique_de_pertes([])
        self.assertEqual(capture.exception.champ, 'pertes')
        self.assertIn('somme explicite', str(capture.exception))

    def test_poste_non_source_est_publie_et_nomme(self):
        politique = politique_de_pertes(
            [{'poste': 'availability', 'pct': 1.0, 'source': None}])
        self.assertEqual(politique.postes_non_sources, ('availability',))
        self.assertIsNone(politique.publication()['pertes'][0]['source'])

    def test_source_inconnue_refusee_en_nommant_le_poste(self):
        with self.assertRaises(PertesInvalides) as capture:
            politique_de_pertes(
                [{'poste': 'soiling', 'pct': 2.0, 'source': 'au_pif'}])
        self.assertEqual(capture.exception.champ, 'soiling')
        self.assertIn('Source inconnue', str(capture.exception))

    def test_doublon_refuse_car_il_serait_compte_deux_fois(self):
        with self.assertRaises(PertesInvalides) as capture:
            politique_de_pertes(
                [{'poste': 'soiling', 'pct': 2.0, 'source': 'saisie'},
                 {'poste': 'soiling', 'pct': 3.0, 'source': 'saisie'}])
        self.assertEqual(capture.exception.champ, 'soiling')

    def test_pourcentage_illisible_ou_hors_bornes_refuse(self):
        for mauvais in ('beaucoup', None, -1, 100, 140):
            with self.subTest(pct=mauvais):
                with self.assertRaises(PertesInvalides) as capture:
                    politique_de_pertes([{'poste': 'wiring', 'pct': mauvais,
                                          'source': 'saisie'}])
                self.assertEqual(capture.exception.champ, 'wiring')

    def test_somme_au_dela_de_cent_pour_cent_refusee(self):
        with self.assertRaises(PertesInvalides) as capture:
            politique_de_pertes(
                [{'poste': 'a', 'pct': 60.0, 'source': 'saisie'},
                 {'poste': 'b', 'pct': 45.0, 'source': 'saisie'}])
        self.assertEqual(capture.exception.champ, 'pertes')


# ── Le balayage de surface ────────────────────────────────────────────────
#: Les constantes NOMMÉES du site public qui portent le défaut interdit : leur
#: simple présence dans le module serait une perte cachée, où qu'elle soit.
CONSTANTES_INTERDITES = (
    'PVGIS_BUILTIN_LOSS', 'SYSTEM_LOSS_TOTAL', 'PRODUCTION_DERATE',
    'PRODUCTIBLE_NET_FACTOR', 'PRODUCTION_NET_FACTOR', 'PVGIS_LIVE_LOSS_PCT',
)

#: Un littéral utilisé COMME une perte : ``loss=14``, ``'loss': 20``,
#: ``perte_defaut = 0.14``…
LITTERAL_DE_PERTE = re.compile(
    r"""(?ix)
    (?:['"]?\b(?:loss|pertes?|perte_\w+|\w+_loss|\w+_perte)\b['"]?)
    \s*[:=]\s*
    -?\d+(?:\.\d+)?
    """)

#: Un littéral interdit posé sur une ligne qui parle de pertes.
VALEURS_INTERDITES = re.compile(r'(?<![\w.])(?:0\.14|0\.2|14|20)(?![\w.])')
MOT_DE_PERTE = re.compile(r'(?i)\b(?:loss|perte)')


def _fichiers_du_module():
    racine = pathlib.Path(__file__).resolve().parent.parent
    for chemin in sorted(racine.rglob('*.py')):
        parties = chemin.relative_to(racine).parts
        if 'migrations' in parties:
            continue
        # Le fichier de test qui PORTE la règle cite forcément les littéraux
        # interdits (il ne pourrait pas les interdire sinon) : il est le seul
        # exclu, et il est nommé ici pour que l'exclusion reste visible.
        if chemin.name == pathlib.Path(__file__).name:
            continue
        yield chemin


class AucunePerteCacheeTest(unittest.TestCase):
    """Aucun 14 % ni 20 % caché ne subsiste dans ``apps/calepinage``."""

    def test_aucune_constante_de_perte_du_site_public(self):
        fautifs = []
        for chemin in _fichiers_du_module():
            texte = chemin.read_text(encoding='utf-8')
            for constante in CONSTANTES_INTERDITES:
                if constante in texte:
                    fautifs.append(f'{chemin.name}: {constante}')
        self.assertEqual(fautifs, [], msg=(
            'Une constante de perte du site public a été recopiée dans le '
            'module : la perte doit être la SOMME des postes, jamais une '
            'constante importée.'))

    def test_aucun_litteral_de_perte_en_dur(self):
        fautifs = []
        for chemin in _fichiers_du_module():
            for numero, ligne in enumerate(
                    chemin.read_text(encoding='utf-8').splitlines(), start=1):
                nu = ligne.strip()
                if nu.startswith('#'):
                    continue
                suspect = LITTERAL_DE_PERTE.search(ligne)
                if suspect is None and MOT_DE_PERTE.search(ligne):
                    suspect = VALEURS_INTERDITES.search(ligne)
                if suspect is not None:
                    fautifs.append(f'{chemin.name}:{numero}: {nu}')
        self.assertEqual(fautifs, [], msg=(
            'Une perte chiffrée en dur a été trouvée : la valeur « loss » '
            'passée à PVGIS est TOUJOURS la somme des postes publiés '
            '(CAL238).'))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
