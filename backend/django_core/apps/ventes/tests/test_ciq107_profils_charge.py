"""CIQ107 — profils de charge de repli : archétypes SOURCÉS seulement.

``unittest`` pur : aucune base, aucun Django (le module testé est pur).
"""

import ast
import json
import os
import unittest

from apps.ventes.moteur_ci import profils
from apps.ventes.moteur_ci.profils import (
    MOTIF_PROFIL_DECLARE, SAISONS, TYPES_JOUR, donnees_archetypes, forme_archetype,
)

ICI = os.path.dirname(os.path.abspath(__file__))
CONTRAT = os.path.join(os.path.dirname(ICI), 'contract_samples', 'etude_ci_preview.json')
PAQUET = os.path.dirname(os.path.abspath(profils.__file__))
#: CIQ110/CIQ116 (re-pin) — le paquet réutilise des modules PURS hors de lui
#: (croisement ``solar_design``, doctrine ``dimensionnement``, ``core.electrique``,
#: constantes 82-21, plages ONEE) : la garde interdit l'import DIRECT de Django
#: ou d'un modèle, et vérifie TRANSITIVEMENT (interpréteur neuf) qu'aucun module
#: du paquet ne charge Django, DRF, Celery ni un ``models``.
RACINES_INTERDITES = ('django', 'rest_framework', 'celery', 'authentication')
IMPORTS_PURS_PERMIS = frozenset({'apps.parametres.pvgis_profils'})


def _contrat_archetypes():
    with open(CONTRAT, encoding='utf-8') as fh:
        return json.load(fh)['donnees_archetypes']


class TestArchetypes(unittest.TestCase):

    def test_bureau_g1_avec_source_et_licence(self):
        forme, source = forme_archetype('bureau', 'ouvre', 'hiver')
        self.assertEqual(len(forme), 24)
        self.assertEqual(source['type'], 'archetype')
        self.assertEqual(source['jeu_de_donnees'], 'BDEW G1')
        self.assertIn('selp_series.csv', source['fichier'])
        self.assertIn('MIT', source['licence'])
        self.assertTrue(source['date_releve'])
        self.assertEqual(source['statut'], 'estimation')
        # un bureau consomme le jour : l'heure 10 pèse plus que l'heure 3
        self.assertGreater(forme[10], forme[3])

    def test_correspondances_categories(self):
        attendus = {
            'bureau': 'BDEW G1', 'boulangerie': 'BDEW G5', 'froid': 'BDEW G3',
            'commerce': 'BDEW G4', 'restaurant': 'BDEW G2',
        }
        for categorie, jeu in attendus.items():
            _forme, source = forme_archetype(categorie, 'samedi', 'ete')
            self.assertEqual(source['jeu_de_donnees'], jeu, categorie)
        for categorie, nom in (('hotel', 'small hotel'), ('sante', 'outpatient'),
                               ('ecole', 'primary school')):
            _forme, source = forme_archetype(categorie, 'dimanche', 'transition')
            self.assertIn('ComStock', source['jeu_de_donnees'])
            self.assertIn(nom, source['jeu_de_donnees'])
            self.assertIn('CC BY 4.0', source['licence'])

    def test_sans_archetype_profil_declare_exige(self):
        for categorie in ('hammam', 'autre', 'industriel', None, 'inconnue'):
            forme, motif = forme_archetype(categorie, 'ouvre', 'hiver')
            self.assertIsNone(forme, categorie)
            self.assertIn(MOTIF_PROFIL_DECLARE, motif)

    def test_chaque_forme_somme_a_un(self):
        for archetype in donnees_archetypes()['archetypes']:
            for type_jour in TYPES_JOUR:
                for saison in SAISONS:
                    forme = archetype['forme'][type_jour][saison]
                    self.assertEqual(len(forme), 24)
                    self.assertTrue(all(v >= 0 for v in forme))
                    self.assertAlmostEqual(sum(forme), 1.0, delta=1e-9,
                                           msg=f"{archetype['cle']} {type_jour} {saison}")

    def test_profil_societe_passe_devant(self):
        courbe = [0] * 8 + [1] * 10 + [0] * 6
        profil = {'cle': 'bureau-maison', 'libelle': 'Bureau maison',
                  'courbe': {'annuel': courbe}, 'provenance': 'relevé compteur 2025'}
        forme, source = forme_archetype('bureau', 'ouvre', 'ete', profil_societe=profil)
        self.assertEqual(source['type'], 'profil_societe')
        self.assertEqual(source['provenance'], 'relevé compteur 2025')
        self.assertAlmostEqual(sum(forme), 1.0, delta=1e-9)
        self.assertEqual(forme[0], 0)
        self.assertAlmostEqual(forme[9], 0.1)
        # même pour une catégorie sans archétype
        forme, source = forme_archetype('hammam', 'dimanche', 'transition', profil_societe=profil)
        self.assertEqual(source['type'], 'profil_societe')

    def test_profil_societe_segmente_par_jour(self):
        profil = {'cle': 'x', 'libelle': 'x', 'provenance': 'p',
                  'courbe': {'hiver': {'ouvre': [1] * 24}}}
        _forme, source = forme_archetype('bureau', 'ouvre', 'hiver', profil_societe=profil)
        self.assertEqual(source['type'], 'profil_societe')
        # pas de courbe week-end saisie : l'archétype reprend la main
        _forme, source = forme_archetype('bureau', 'samedi', 'hiver', profil_societe=profil)
        self.assertEqual(source['type'], 'archetype')

    def test_aucune_part_diurne(self):
        texte = json.dumps(donnees_archetypes())
        self.assertNotIn('part_diurne', texte)
        self.assertNotIn('day_share', texte)
        _forme, source = forme_archetype('bureau', 'ouvre', 'hiver')
        self.assertFalse(any('diurne' in cle for cle in source))


class TestFormeContrat(unittest.TestCase):

    def test_fichier_vendorise_respecte_le_contrat(self):
        contrat = _contrat_archetypes()
        modele = contrat['forme'][0]
        archetypes = donnees_archetypes()['archetypes']
        self.assertTrue(archetypes)
        for archetype in archetypes:
            self.assertEqual(set(archetype), set(modele), archetype['cle'])
            self.assertEqual(set(archetype['source']), set(modele['source']), archetype['cle'])
            self.assertEqual(archetype['statut'], modele['statut'])
            self.assertEqual(set(archetype['forme']), set(TYPES_JOUR))
            for par_saison in archetype['forme'].values():
                self.assertEqual(set(par_saison), set(SAISONS))
            # licence vérifiée, jamais « à vérifier »
            self.assertNotIn('vérifier', archetype['source']['licence'])
        # les catégories sans archétype du contrat n'en reçoivent aucun
        couvertes = {c for a in archetypes for c in a['categories']}
        for categorie in contrat['categories_sans_archetype']:
            self.assertNotIn(categorie.split()[-1], couvertes)

    def test_une_attribution_par_jeu_de_donnees(self):
        donnees = donnees_archetypes()
        attributions = donnees['attributions']
        self.assertEqual(len(attributions), 2)
        self.assertTrue(any('BDEW' in a and 'MIT' in a for a in attributions))
        self.assertTrue(any('ComStock' in a and 'CC BY 4.0' in a for a in attributions))


class TestPurete(unittest.TestCase):
    """Garde AST (patron AGR109) : le paquet moteur_ci n'importe ni Django ni un modèle."""

    def test_aucun_import_django_ni_modele(self):
        fautifs = []
        for nom in sorted(os.listdir(PAQUET)):
            if not nom.endswith('.py'):
                continue
            with open(os.path.join(PAQUET, nom), encoding='utf-8') as fh:
                arbre = ast.parse(fh.read(), filename=nom)
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    modules = [alias.name for alias in noeud.names]
                elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
                    modules = [noeud.module or '']
                else:
                    continue
                for module in modules:
                    if module.startswith('apps.ventes.moteur_ci') or module in IMPORTS_PURS_PERMIS:
                        continue
                    if module.split('.')[0] in RACINES_INTERDITES or 'models' in module:
                        fautifs.append((nom, module))
        self.assertEqual(fautifs, [])

    def test_imports_permis_sans_django(self):
        """Interpréteur NEUF (sans réglages Django) : importer tout le paquet ne
        charge ni Django, ni DRF, ni Celery, ni aucun ``models``."""
        import subprocess
        import sys
        racine = os.path.dirname(os.path.dirname(os.path.dirname(PAQUET)))
        script = (
            'import importlib, pkgutil, sys\n'
            'import apps.ventes.moteur_ci as p\n'
            'for m in pkgutil.iter_modules(p.__path__):\n'
            '    importlib.import_module("apps.ventes.moteur_ci." + m.name)\n'
            'print(sorted(k for k in sys.modules if k.split(".")[0] in '
            '("django", "rest_framework", "celery") or k.endswith(".models")))\n')
        env = {k: v for k, v in os.environ.items() if k != 'DJANGO_SETTINGS_MODULE'}
        sortie = subprocess.run([sys.executable, '-c', script], cwd=racine, env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(sortie.returncode, 0, sortie.stderr[-2000:])
        self.assertEqual(sortie.stdout.strip(), '[]')

    def test_garde_armee(self):
        arbre = ast.parse('from django.db import models\n')
        noeud = arbre.body[0]
        self.assertIn(noeud.module.split('.')[0], RACINES_INTERDITES)


if __name__ == '__main__':
    unittest.main()
