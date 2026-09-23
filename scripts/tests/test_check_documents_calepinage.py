"""Tests CALX329 — scripts/check_documents_calepinage.py.

Stdlib pure (unittest), sans Django ni base : la garde elle-même n'en a pas
besoin (analyse ``ast`` de fichiers source, jamais un import de
``apps.calepinage``). Chaque cas NÉGATIF prouve que la garde rougit
vraiment — en particulier qu'elle échoue si l'on retire un rendu SANS
retirer sa déclaration (le Done= littéral de CALX329) — et le dernier prouve
qu'elle est VERTE sur le dépôt RÉEL (une garde qui ne peut plus rougir et
une garde déjà rouge sont toutes les deux inutilisables).

Run :
    python -m unittest scripts.tests.test_check_documents_calepinage -v
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import check_documents_calepinage as cdc  # noqa: E402


class CodesTupleDeTuplesTest(unittest.TestCase):
    """``_codes_tuple_de_tuples`` — le patron ``SPEC_PIECES``/
    ``PIECES_PRODUITES``/``_DEFINITIONS_DOCUMENTS``."""

    def test_extrait_le_premier_element_de_chaque_ligne(self):
        arbre = ast.parse(
            "SPEC_PIECES = (\n"
            "    ('planche', 'Planche', True),\n"
            "    ('note_calcul', 'Note de calcul', True),\n"
            ")\n")
        self.assertEqual(
            cdc._codes_tuple_de_tuples(arbre, 'SPEC_PIECES'),
            ['planche', 'note_calcul'])

    def test_variable_renommee_leve_lookuperror_en_la_nommant(self):
        arbre = ast.parse("AUTRE_NOM = (('x', 'y', True),)\n")
        with self.assertRaises(LookupError) as capture:
            cdc._codes_tuple_de_tuples(arbre, 'SPEC_PIECES')
        self.assertIn('SPEC_PIECES', str(capture.exception))


class ClesReturnDictTest(unittest.TestCase):
    """``_cles_return_dict`` — le patron
    ``def _rendus(...): return {...}``."""

    def test_extrait_les_cles_du_dict_retourne(self):
        arbre = ast.parse(
            "def _rendus(calepinage, company):\n"
            "    return {\n"
            "        'planche': lambda: None,\n"
            "        'note_calcul': lambda: None,\n"
            "    }\n")
        self.assertEqual(
            sorted(cdc._cles_return_dict(arbre, '_rendus')),
            ['note_calcul', 'planche'])

    def test_fonction_absente_leve_lookuperror(self):
        arbre = ast.parse("def autre_fonction():\n    return {}\n")
        with self.assertRaises(LookupError) as capture:
            cdc._cles_return_dict(arbre, '_rendus')
        self.assertIn('_rendus', str(capture.exception))

    def test_fonction_sans_return_dict_litteral_leve_lookuperror(self):
        arbre = ast.parse(
            "def _rendus(calepinage, company):\n"
            "    variable = construire()\n"
            "    return variable\n")
        with self.assertRaises(LookupError):
            cdc._cles_return_dict(arbre, '_rendus')


class ClesRegistreModuleTest(unittest.TestCase):
    """``_cles_registre_module`` — le patron ``MISES_EN_PAGE`` : un dict
    initial PUIS des lignes ``REGISTRE['code'] = ...`` ajoutées plus loin
    dans le fichier (surface APPEND-ONLY, ``services/documents/__init__
    .py``)."""

    def test_cumule_le_dict_initial_et_les_lignes_ajoutees(self):
        arbre = ast.parse(
            "MISES_EN_PAGE = {\n"
            "    'rapport_etude': 'x:y',\n"
            "}\n"
            "\n"
            "MISES_EN_PAGE['plan_cablage'] = 'a:b'\n"
            "MISES_EN_PAGE['manuel_proprietaire'] = 'c:d'\n")
        self.assertEqual(
            sorted(cdc._cles_registre_module(arbre, 'MISES_EN_PAGE')),
            ['manuel_proprietaire', 'plan_cablage', 'rapport_etude'])

    def test_registre_absent_leve_lookuperror(self):
        arbre = ast.parse("AUTRE = {}\n")
        with self.assertRaises(LookupError):
            cdc._cles_registre_module(arbre, 'MISES_EN_PAGE')


class EcartsDeFamilleTest(unittest.TestCase):
    """``ecarts_de_famille``/``problemes_de_famille`` — PURS, aucun fichier
    touché : le cœur de la garde, testé en une ligne par cas."""

    def test_un_code_declare_sans_rendu_ni_exemption_est_manquant(self):
        manquants, orphelins = cdc.ecarts_de_famille(
            declares=['planche', 'note_calcul'],
            rendus=['planche'],
            exemptions={})
        self.assertEqual(manquants, ['note_calcul'])
        self.assertEqual(orphelins, [])

    def test_un_motif_produit_ailleurs_non_vide_neutralise_le_manque(self):
        manquants, _ = cdc.ecarts_de_famille(
            declares=['planche', 'export_projet_json'],
            rendus=['planche'],
            exemptions={'export_projet_json': 'format JSON, hors HTML.'})
        self.assertEqual(manquants, [])

    def test_un_motif_vide_ne_neutralise_rien(self):
        # Un motif blanc ("" ou espaces) n'est PAS une exemption réelle —
        # jamais un silence qui se fait passer pour un motif.
        manquants, _ = cdc.ecarts_de_famille(
            declares=['planche'], rendus=[], exemptions={'planche': '   '})
        self.assertEqual(manquants, ['planche'])

    def test_un_rendu_sans_declaration_est_orphelin(self):
        _, orphelins = cdc.ecarts_de_famille(
            declares=['planche'], rendus=['planche', 'fantome'],
            exemptions={})
        self.assertEqual(orphelins, ['fantome'])

    def test_le_defaut_de_calx309_est_bien_detecte(self):
        # Reproduction EXACTE du Constat de CALX329 : SPEC_PIECES declarait
        # 4 pieces, `_rendus` n'en mappait que 2 — RIEN ne le voyait.
        problemes = cdc.problemes_de_famille(
            'pack_technique', 'pack_technique.py',
            declares=['planche', 'note_calcul', 'plan_toiture',
                      'plan_masse'],
            rendus=['planche', 'note_calcul'],
            exemptions={})
        self.assertTrue(
            any('plan_toiture' in p for p in problemes), problemes)
        self.assertTrue(
            any('plan_masse' in p for p in problemes), problemes)

    def test_une_exemption_orpheline_est_nommee_comme_un_filtre_mort(self):
        problemes = cdc.problemes_de_famille(
            'documents', 'documents/__init__.py',
            declares=['rapport_etude'],
            rendus=['rapport_etude'],
            exemptions={'code_disparu': 'motif quelconque'})
        self.assertTrue(
            any('code_disparu' in p and 'filtre mort' in p
                for p in problemes),
            problemes)


class RetirerUnRenduSansRetirerSaDeclarationTest(unittest.TestCase):
    """Le Done= LITTÉRAL de CALX329 : « la garde échoue si l'on retire un
    rendu sans retirer sa déclaration »."""

    def test_retirer_une_cle_du_dict_de_rendu_fait_rougir_la_garde(self):
        declares = ['planche', 'note_calcul', 'plan_toiture', 'plan_masse',
                    'rapport_etude', 'plan_cablage', 'rapport_ombrage']
        rendus_complets = list(declares)
        self.assertEqual(cdc.ecarts_de_famille(
            declares, rendus_complets, {})[0], [])

        rendus_ampute = [c for c in rendus_complets if c != 'plan_cablage']
        manquants, _ = cdc.ecarts_de_famille(declares, rendus_ampute, {})
        self.assertEqual(manquants, ['plan_cablage'])


class DepotReelTest(unittest.TestCase):
    """La garde tourne sur le DÉPÔT RÉEL — verte après CALX309 et CALX326,
    exactement comme le Done= de CALX329 l'exige."""

    def test_verifier_ne_trouve_aucun_ecart_sur_le_depot_reel(self):
        problemes = cdc.verifier()
        self.assertEqual(problemes, [], problemes)

    def test_pack_technique_declare_sept_pieces_toutes_rendues(self):
        arbre = cdc._arbre(ROOT / 'backend' / 'django_core' / 'apps'
                           / 'calepinage' / 'services' / 'pack_technique.py')
        declares = cdc._codes_tuple_de_tuples(arbre, 'SPEC_PIECES')
        rendus = cdc._cles_return_dict(arbre, '_rendus')
        self.assertEqual(set(declares), set(rendus))
        self.assertGreaterEqual(len(declares), 7)

    def test_chaque_exemption_documents_correspond_a_un_code_reel(self):
        arbre = cdc._arbre(
            ROOT / 'backend' / 'django_core' / 'apps' / 'calepinage'
            / 'services' / 'documents' / '__init__.py')
        declares = set(cdc._codes_tuple_de_tuples(
            arbre, '_DEFINITIONS_DOCUMENTS'))
        for code in cdc.PRODUIT_AILLEURS.get('documents', {}):
            self.assertIn(code, declares, code)

    def test_main_rend_zero_sur_le_depot_reel(self):
        import io
        from contextlib import redirect_stdout

        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code_retour = cdc.main()
        self.assertEqual(code_retour, 0, tampon.getvalue())


class MainRougitSurUnEcartTest(unittest.TestCase):
    """``main()`` bout en bout — ``verifier`` REMPLACÉ (``unittest.mock``,
    aucun fichier réel touché) par une liste de problèmes synthétique, pour
    prouver que ``main`` FORMATE et REND 1 dès qu'il y en a."""

    def test_main_rend_un_et_nomme_l_ecart_quand_verifier_en_trouve(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock

        tampon = io.StringIO()
        with mock.patch.object(
                cdc, 'verifier',
                return_value=["pack_technique (pack_technique.py) : "
                              "« note_calcul » est DÉCLARÉ sans rendu."]):
            with redirect_stdout(tampon):
                code_retour = cdc.main()
        self.assertEqual(code_retour, 1)
        self.assertIn('note_calcul', tampon.getvalue())

    def test_main_rend_zero_quand_verifier_ne_trouve_rien(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock

        tampon = io.StringIO()
        with mock.patch.object(cdc, 'verifier', return_value=[]):
            with redirect_stdout(tampon):
                code_retour = cdc.main()
        self.assertEqual(code_retour, 0)


if __name__ == '__main__':
    unittest.main()
