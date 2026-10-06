"""CIQ625 — ``core.recette.resultat`` : la règle PURE du résultat de recette.

Sans base de données (SimpleTestCase) : la fonction est stdlib seule.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from core.recette import resultat as R


class ResultatRecetteTests(SimpleTestCase):

    def test_un_essai_faux_non_conforme(self):
        self.assertEqual(R.resultat_recette([True, False, True]),
                         R.NON_CONFORME)
        self.assertEqual(R.resultat_recette([None, False]), R.NON_CONFORME)

    def test_tous_vrais_conforme(self):
        self.assertEqual(R.resultat_recette([True, True, True]), R.CONFORME)

    def test_un_essai_null_en_cours(self):
        self.assertEqual(R.resultat_recette([True, None, True]), R.EN_COURS)

    def test_aucun_essai_en_cours(self):
        self.assertEqual(R.resultat_recette([]), R.EN_COURS)

    def test_un_choix_autre_que_reserves_est_ignore(self):
        self.assertEqual(R.resultat_avec_choix([True, False], 'conforme'),
                         R.NON_CONFORME)
        self.assertEqual(R.resultat_avec_choix([True, None], 'conforme'),
                         R.EN_COURS)

    def test_reserves_admis_seulement_si_tous_vrais(self):
        self.assertEqual(R.resultat_avec_choix([True, True], R.RESERVES),
                         R.RESERVES)
        for essais in ([True, False], [True, None]):
            with self.subTest(essais=essais):
                with self.assertRaises(R.ReservesRefusees) as leve:
                    R.resultat_avec_choix(essais, R.RESERVES)
                self.assertIn('réserves', str(leve.exception))

    def test_module_pur_aucun_import_apps_ni_django(self):
        """Fondation : stdlib seule (contrat import-linter `core`)."""
        dossier = Path(R.__file__).resolve().parent
        for fichier in dossier.glob('*.py'):
            arbre = ast.parse(fichier.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                noms = []
                if isinstance(noeud, ast.Import):
                    noms = [a.name for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    noms = [noeud.module or '']
                for nom in noms:
                    with self.subTest(fichier=fichier.name, nom=nom):
                        self.assertFalse(nom.startswith(('apps', 'django')))
