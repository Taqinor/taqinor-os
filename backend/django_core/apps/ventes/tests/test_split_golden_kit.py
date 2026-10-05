"""SPL240 — auto-vérification du kit de preuve « move only » (split_golden.py).

Tests sur de VRAIS modules temporaires (aucun mock de la fonction testée) :
une copie fidèle déplacée dans un sous-paquet reste verte malgré un
``ImportFrom.level`` différent ; une instruction modifiée rougit ; un symbole
resté dans la source rougit ; un golden vide rougit ; un groupe sans fichier
échoue bruyamment.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_split_golden_kit -v 2
"""
import datetime
import tempfile
import textwrap
import unittest
import uuid
from pathlib import Path

from apps.ventes.tests import split_golden as sg

SOURCE = textwrap.dedent('''\
    import logging
    from .services import calculer
    from . import selectors as sel

    LIMITE = 3


    def _aide(x):
        """Docstring conservée."""
        from .models import Devis
        return calculer(x) + LIMITE + len(Devis.__name__)


    @staticmethod
    def _decoree():
        return sel


    class Garde:
        seuil = 2

        def ok(self):
            from ..domain import regles
            return regles
    ''')

# Copie fidèle dans un sous-paquet : seuls les niveaux d'import relatifs changent.
CIBLE_FIDELE = textwrap.dedent('''\
    from ..services import calculer
    from .. import selectors as sel

    LIMITE = 3


    def _aide(x):
        """Docstring conservée."""
        from ..models import Devis
        return calculer(x) + LIMITE + len(Devis.__name__)


    @staticmethod
    def _decoree():
        return sel


    class Garde:
        seuil = 2

        def ok(self):
            from ...domain import regles
            return regles
    ''')

SOURCE_VIDEE = 'import logging\nfrom .sous.cible import _aide, LIMITE, Garde, _decoree\n'

SYMBOLES = ['LIMITE', '_aide', '_decoree', 'Garde']


class KitSplitGoldenTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name)
        self.golden = self.racine / 'golden'
        (self.racine / 'sous').mkdir()
        self.source = self.racine / 'source.py'
        self.cible = self.racine / 'sous' / 'cible.py'
        self.source.write_text(SOURCE, encoding='utf-8')
        sg.ecrire_golden('demo', sg.empreintes(self.source, SYMBOLES), dossier=self.golden)

    def tearDown(self):
        self._tmp.cleanup()

    def _deplacer(self, texte_cible, texte_source=SOURCE_VIDEE):
        self.cible.write_text(texte_cible, encoding='utf-8')
        self.source.write_text(texte_source, encoding='utf-8')

    def test_golden_trie_et_relu(self):
        brut = (self.golden / 'demo.json').read_text(encoding='utf-8')
        self.assertTrue(brut.endswith('\n'))
        relu = sg.charger_golden('demo', dossier=self.golden)
        self.assertEqual(sorted(relu), sorted(SYMBOLES))
        self.assertEqual(list(relu), sorted(relu))

    def test_rouge_avant_deplacement(self):
        self.cible.write_text('', encoding='utf-8')
        with self.assertRaises(AssertionError):
            sg.verifier_deplacement('demo', self.cible, self.source, dossier=self.golden)

    def test_copie_fidele_verte_malgre_level(self):
        self._deplacer(CIBLE_FIDELE)
        sg.verifier_deplacement('demo', self.cible, self.source, dossier=self.golden)

    def test_instruction_modifiee_rouge(self):
        self._deplacer(CIBLE_FIDELE.replace('+ LIMITE +', '- LIMITE +'))
        ecarts = sg.ecarts_deplacement('demo', self.cible, self.source, dossier=self.golden)
        self.assertEqual(ecarts, [f'_aide : empreinte différente dans {self.cible}'])

    def test_docstring_et_decorateur_comptent(self):
        self._deplacer(CIBLE_FIDELE.replace('Docstring conservée.', 'Autre.')
                       .replace('@staticmethod\n', ''))
        ecarts = sg.ecarts_deplacement('demo', self.cible, self.source, dossier=self.golden)
        self.assertEqual(len(ecarts), 2)

    def test_module_importe_change_rouge(self):
        self._deplacer(CIBLE_FIDELE.replace('from ..models import Devis',
                                            'from ..autres import Devis'))
        with self.assertRaises(AssertionError):
            sg.verifier_deplacement('demo', self.cible, self.source, dossier=self.golden)

    def test_symbole_reste_dans_source_rouge(self):
        self._deplacer(CIBLE_FIDELE, SOURCE)  # jumeau : copié mais pas supprimé
        ecarts = sg.ecarts_deplacement('demo', self.cible, self.source, dossier=self.golden)
        self.assertEqual(len(ecarts), len(SYMBOLES))
        self.assertTrue(all('encore défini dans la source' in e for e in ecarts))

    def test_import_pour_usage_dans_source_reste_vert(self):
        # La source importe les noms déplacés : ce n'est pas une DÉFINITION.
        self._deplacer(CIBLE_FIDELE)
        self.assertIn('_aide', SOURCE_VIDEE)
        self.assertEqual(sg.symboles_de_niveau_module(self.source), set())

    def test_golden_vide_rouge(self):
        sg.ecrire_golden('vide', {}, dossier=self.golden)
        self._deplacer(CIBLE_FIDELE)
        with self.assertRaises(AssertionError):
            sg.verifier_deplacement('vide', self.cible, self.source, dossier=self.golden)

    def test_capture_incomplete_rouge(self):
        with self.assertRaises(AssertionError):
            sg.empreintes(self.source, ['_inexistant'])

    def test_golden_absent_rouge(self):
        with self.assertRaises(AssertionError):
            sg.charger_golden('absent', dossier=self.golden)

    def test_groupe_vide_echec_bruyant(self):
        with self.assertRaises(AssertionError):
            sg.fichiers_du_groupe('rien.py', 'nulle_part/*.py', base=self.racine)

    def test_groupe_et_source_du_symbole(self):
        self._deplacer(CIBLE_FIDELE)
        groupe = sg.fichiers_du_groupe('source.py', 'sous/*.py', base=self.racine)
        self.assertEqual(groupe, sorted([self.source, self.cible]))
        segment = sg.source_du_symbole('_decoree', groupe)
        self.assertTrue(segment.startswith('@staticmethod\ndef _decoree():'))
        with self.assertRaises(AssertionError):
            sg.source_du_symbole('_absent', groupe)

    def test_source_du_symbole_jumeau_rouge(self):
        self._deplacer(CIBLE_FIDELE, SOURCE)
        groupe = sg.fichiers_du_groupe('source.py', 'sous/*.py', base=self.racine)
        with self.assertRaises(AssertionError):
            sg.source_du_symbole('_aide', groupe)

    def test_digest_normalise(self):
        a = {'id': 1, 'token': 'abc', 'cree': datetime.datetime(2026, 1, 1),
             'lien': f'/p/{uuid.uuid4()}/', 'montant': 10}
        b = {'id': 2, 'token': 'xyz', 'cree': datetime.datetime(2027, 5, 5),
             'lien': f'/p/{uuid.uuid4()}/', 'montant': 10}
        self.assertEqual(sg.digest(a), sg.digest(b))
        self.assertNotEqual(sg.digest(a), sg.digest(dict(b, montant=11)))
        self.assertNotEqual(sg.digest({'id': 1}), sg.digest({'id': 1}, cles_ids=()))
