"""Tests CRX20 — le cliquet « assignation scalaire d'etape » de
scripts/check_stages.py.

Stdlib pure (unittest), sans Django ni base : la garde elle-meme n'en a pas.
Chaque cas NEGATIF prouve que la garde rougit vraiment ; les cas POSITIFS
prouvent qu'elle ne rougit pas sur les ecritures correctes (sinon elle serait
deja rouge sur le depot, donc inutilisable). La verte-sur-le-depot-reel n'est
pas rejouee ici : le job CI `stage-names` execute deja check_stages.py sur
l'arbre complet a chaque push, et un second balayage rglob doublerait ce cout
pour zero information supplementaire.

Run:
    python -m unittest scripts.tests.test_check_stages -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_stages as cs  # noqa: E402


def _ecritures(texte):
    """Litteraux d'etape captures par le cliquet dans ``texte``."""
    return [m.group(2) for m in cs.SCALAR_ASSIGN_RE.finditer(texte)]


class TestAssignationScalaire(unittest.TestCase):
    def test_litteral_en_dur_est_capture(self):
        self.assertEqual(
            _ecritures("lead.stage = 'FOLLOW_UP'"), ['FOLLOW_UP'])
        self.assertEqual(
            _ecritures('lead.stage = "COLD"'), ['COLD'])

    def test_espacement_et_guillemets_indifferents(self):
        self.assertEqual(
            _ecritures("self.lead.stage='QUOTE_SENT'"), ['QUOTE_SENT'])
        self.assertEqual(
            _ecritures("obj.stage   =   'SIGNED'"), ['SIGNED'])

    def test_ecriture_par_la_constante_ne_rougit_pas(self):
        # La forme CORRECTE — celle vers laquelle la garde pousse.
        self.assertEqual(_ecritures('lead.stage = stages.FOLLOW_UP'), [])
        self.assertEqual(_ecritures('lead.stage = cible'), [])

    def test_comparaison_ne_rougit_pas(self):
        # Une comparaison est une LECTURE : hors perimetre du cliquet, qui
        # vise les ecritures qui deplacent un lead dans le funnel.
        self.assertEqual(_ecritures("if lead.stage == 'COLD':"), [])
        self.assertEqual(_ecritures("lead.stage != 'NEW'"), [])

    def test_autre_champ_ne_rougit_pas(self):
        self.assertEqual(_ecritures("lead.canal = 'NEW'"), [])
        self.assertEqual(_ecritures("stage = 'NEW'"), [])


class TestFiltrageCanonique(unittest.TestCase):
    """Seuls les 6 noms canoniques comptent : un homonyme n'est pas une etape."""

    def setUp(self):
        self.canonique = set(cs.load_canonical())

    def test_les_six_cles_sont_capturees(self):
        for cle in self.canonique:
            with self.subTest(cle=cle):
                captures = _ecritures("lead.stage = '%s'" % cle)
                self.assertEqual(captures, [cle])
                self.assertIn(captures[0], self.canonique)

    def test_valeur_hors_canon_est_ignoree(self):
        captures = _ecritures("etape.stage = 'BROUILLON'")
        self.assertEqual(captures, ['BROUILLON'])
        # La boucle de main() ne retient que les valeurs canoniques.
        self.assertNotIn('BROUILLON', self.canonique)


class TestExemptionTests(unittest.TestCase):
    """Les modules de test peuvent epingler un litteral a dessein."""

    def test_fichiers_de_test_exemptes(self):
        for nom in ('tests.py', 'tests_crx20_stage_events.py',
                    'test_quelque_chose.py', 'quelque_chose_test.py',
                    'conftest.py', 'Panel.test.jsx'):
            with self.subTest(nom=nom):
                self.assertTrue(
                    cs.is_test_file(Path('backend/apps/crm') / nom), nom)

    def test_dossier_tests_exempte(self):
        self.assertTrue(
            cs.is_test_file(Path('backend/apps/compta/tests/test_x.py')))

    def test_fichier_de_production_non_exempte(self):
        for nom in ('services.py', 'recouvrement.py', 'models.py',
                    'latest_news.py'):
            with self.subTest(nom=nom):
                self.assertFalse(
                    cs.is_test_file(Path('backend/apps/crm') / nom), nom)


if __name__ == '__main__':
    unittest.main()
