"""ADEP108 — la garde « un seul moteur » (``scripts/check_moteur_unique.py``).

Elle refuse un NOUVEL appel d'un des cinq noyaux (``recommander_taille``, ``etudier_ci``,
``etudier_pompage``, ``calculer_etude_horaire``, ``simuler_calepinage``) hors du moteur
unique et de sa liste figée, et une entrée de la liste qui n'est plus appelée (la liste ne
fait que rétrécir). Pur stdlib, sans Django ni base. Run :
    python -m unittest scripts.tests.test_check_moteur_unique -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_moteur_unique as garde  # noqa: E402


def _arbre(fichiers):
    """Un faux ``apps/`` : ``{chemin relatif à apps: source}`` ; rend le dossier ``apps``."""
    racine = Path(tempfile.mkdtemp()) / 'apps'
    for relatif, source in fichiers.items():
        chemin = racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(source, encoding='utf-8')
    return racine


def _lancer(racine, permis):
    sortie = io.StringIO()
    with redirect_stdout(sortie):
        code = garde.main(racine, permis)
    return code, sortie.getvalue()


class GardeMoteurUniqueTest(unittest.TestCase):

    def test_le_depot_est_vert(self):
        code, sortie = _lancer(garde.APPS, garde.APPELANTS_PERMIS)
        self.assertEqual(code, 0, sortie)

    def test_un_nouvel_appel_hors_liste_echoue_en_nommant_le_fichier(self):
        racine = _arbre({'crm/views.py': 'from apps.ventes.domain.etude_ci import etudier_ci\n\n'
                                         'def vue():\n    return etudier_ci(1)\n'})
        code, sortie = _lancer(racine, {})
        self.assertEqual(code, 1)
        self.assertIn('apps/crm/views.py:4', sortie)
        self.assertIn('etudier_ci', sortie)

    def test_une_entree_perimee_echoue(self):
        racine = _arbre({'crm/views.py': 'def vue():\n    return 1\n'})
        code, sortie = _lancer(racine, {('apps/crm/views.py', 'recommander_taille'): 'ancien'})
        self.assertEqual(code, 1)
        self.assertIn('PÉRIMÉE', sortie)

    def test_moteur_tests_commentaires_et_alias(self):
        racine = _arbre({
            'ventes/conception/moteur.py': 'def m():\n    return recommander_taille()\n',
            'ventes/tests/test_x.py': 'def t():\n    return recommander_taille()\n',
            'crm/note.py': '# recommander_taille()\nTEXTE = "simuler_calepinage()"\n',
            'crm/tache.py': 'from x import simuler_calepinage as tache\n\ndef f():\n    tache.delay(1)\n',
        })
        trouves = garde.releve(racine)
        self.assertEqual(set(trouves), {('apps/crm/tache.py', 'simuler_calepinage')})

    def test_les_cinq_noyaux_sont_surveilles(self):
        # mutant : retirer ``simuler_calepinage`` (ou un autre) des noyaux ⇒ rouge.
        self.assertEqual(set(garde.NOYAUX), {'recommander_taille', 'etudier_ci', 'etudier_pompage',
                                             'calculer_etude_horaire', 'simuler_calepinage'})
        for noyau in garde.NOYAUX:
            self.assertEqual(garde.appels(f'def f():\n    return {noyau}()\n'), [(2, noyau)])

    def test_chaque_entree_dit_pourquoi_elle_reste(self):
        for cle, raison in garde.APPELANTS_PERMIS.items():
            self.assertTrue(raison.strip(), cle)


if __name__ == '__main__':
    unittest.main()
