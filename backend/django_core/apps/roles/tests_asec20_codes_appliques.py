"""ASEC20 — garde inverse du catalogue des droits : chaque code d'écriture /
export du registre a un consommateur serveur.

Sens ``vue -> catalogue`` : ``tests_wir169_catalogue_declare.py`` (un code posé
sur une vue existe au catalogue). Sens ``catalogue -> vue`` : ce module. Un code
affiché dans la grille de rôles que AUCUN code serveur ne vérifie est décoratif :
l'administrateur croit retirer un pouvoir en décochant la case, le serveur
l'accorde quand même (C-ASEC-015 : export CRM sans ``crm_export``, 200).

Méthode : lecture de l'AST (jamais de regex sur le source) de tout
``backend/django_core`` hors tests, migrations, ``golden``, registre lui-même et
catalogue de séparation des tâches (``accessreview/sod.py`` : liste de paires
incompatibles, pas une application). Un code est CONSOMMÉ dès qu'un littéral de
chaîne égal au code apparaît dans ce code serveur : déclaration de permission
(``write_permission = 'x'``), constante de module (``CAL_GERER = 'x'``), argument
de ``HasPermissionOrLegacy``/``has_erp_permission``/``has_perm``, etc.

Périmètre : tous les codes du catalogue SAUF la visibilité ``*_voir``.

Exemptions (décroissantes — jamais d'ajout pour faire passer la garde) :

* module du code PARQUÉ (``core.parked.APPS_PARQUEES``) : l'app n'expose plus
  aucune vue, le code revit avec elle ; l'exemption disparaît seule au retour du
  module ;
* ``EXEMPTIONS`` : code -> raison, une ligne motivée par code. Les « A CORRIGER »
  attendent la garde serveur d'une tâche ASEC nommée ; dès qu'un code y devient
  consommé, ce test échoue (« exemption périmée ») et impose de retirer la ligne.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from apps.roles.permissions_registre import ALL_PERMISSIONS, PERMISSION_MODULE
from core.parked import APPS_PARQUEES

RACINE = Path(__file__).resolve().parent.parent.parent  # backend/django_core

_DOSSIERS_EXCLUS = {'migrations', 'golden', '__pycache__', 'tests', 'node_modules'}
_FICHIERS_EXCLUS = {
    'apps/roles/permissions_registre.py',   # le catalogue lui-même
    'apps/accessreview/sod.py',             # paires incompatibles, pas une application
}

_C015 = ('A CORRIGER (C-ASEC-015, D-ASEC-4) : code affiché dans la grille mais jamais '
         'vérifié côté serveur ; la garde est posée par ASEC29/ASEC31/ASEC50')

#: code -> raison. Décroissant : retirer la ligne dès que le code est consommé.
EXEMPTIONS = {
    'crm_export': _C015,
    'crm_reassign': _C015,
    'crm_supprimer': _C015,
    'installation_export': _C015,
    'intervention_gerer': _C015,
    'reporting_export': _C015,
    'sav_export': _C015,
    'sav_reassign': _C015,
    'stock_export': _C015,
    'technicien_assign': _C015,
    'ventes_export': _C015,
    'ventes_modifier': _C015,
    'ventes_reassign': _C015,
    'ventes_supprimer': _C015,
    'adsengine_flightplan_manage': (
        "A CORRIGER (adsengine, session propriétaire) : plans de vol ADSENG47 "
        "gérés par un palier, aucun littéral du code côté serveur"),
    'emettre_carte_achat': (
        "geste de l'app frais (parquée, cartes d'achat) rangé sous le module stock "
        "du catalogue : aucune vue ne le sert tant que frais est parquée"),
    'records_scope_equipe': (
        "marqueur de portée (pas une action) lu par PRÉFIXE ``records_scope_`` dans "
        "core/scoping.py : narrowing opt-in, jamais comparé au littéral"),
    'records_scope_sous_arbre': (
        "marqueur de portée (pas une action) lu par PRÉFIXE ``records_scope_`` dans "
        "core/scoping.py : narrowing opt-in, jamais comparé au littéral"),
}


def codes_a_garder(codes=None):
    """Codes d'écriture / export du catalogue (hors visibilité ``*_voir``)."""
    return sorted(c for c in (ALL_PERMISSIONS if codes is None else codes)
                  if not c.endswith('_voir'))


def _fichiers_serveur(racine):
    for p in sorted(Path(racine).rglob('*.py')):
        rel = p.relative_to(racine)
        if set(rel.parts) & _DOSSIERS_EXCLUS:
            continue
        nom = p.name
        if nom.startswith(('tests', 'test_')) or nom == 'conftest.py':
            continue
        if rel.as_posix() in _FICHIERS_EXCLUS:
            continue
        yield p, rel.as_posix()


def consommateurs(codes, racine=RACINE):
    """code -> ensemble des fichiers serveur dont l'AST porte ce littéral."""
    visee = set(codes)
    trouves = {c: set() for c in visee}
    for p, rel in _fichiers_serveur(racine):
        try:
            arbre = ast.parse(p.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                    and noeud.value in visee):
                trouves[noeud.value].add(rel)
    return trouves


def sans_consommateur(codes=None, racine=RACINE):
    """Codes sans consommateur, hors modules parqués et exemptions."""
    codes = codes_a_garder(codes)
    trouves = consommateurs(codes, racine)
    out = []
    for c in codes:
        if trouves[c]:
            continue
        if PERMISSION_MODULE.get(c) in APPS_PARQUEES:
            continue
        if c in EXEMPTIONS:
            continue
        out.append(c)
    return out


class CodesAppliquesTests(SimpleTestCase):
    def test_chaque_code_a_un_consommateur(self):
        manquants = sans_consommateur()
        self.assertEqual(
            manquants, [],
            "codes du catalogue sans consommateur serveur (ni module parqué ni "
            f"exemption motivée) : {manquants}. Poser la garde côté serveur "
            "(HasPermissionOrLegacy / write_permission), ne pas décorer la grille.")

    def test_exemptions_non_perimees(self):
        # Un code exempté qui a désormais un consommateur (la garde ASEC est
        # posée), ou qui a quitté le catalogue, impose de retirer sa ligne.
        trouves = consommateurs(list(EXEMPTIONS))
        perimees = sorted(c for c in EXEMPTIONS
                          if c not in ALL_PERMISSIONS or trouves[c])
        self.assertEqual(
            perimees, [],
            f"exemptions périmées à retirer de EXEMPTIONS : {perimees}")

    def test_exemptions_motivees(self):
        for code, raison in EXEMPTIONS.items():
            with self.subTest(code=code):
                self.assertGreaterEqual(len(raison), 40)
                self.assertNotIn(PERMISSION_MODULE.get(code), APPS_PARQUEES,
                                 f"{code}: déjà exempté par module parqué")

    def test_code_encaisser_consomme(self):
        # D-ASEC-1 : le code des gestes d'argent est appliqué côté serveur.
        self.assertTrue(consommateurs(['encaisser'])['encaisser'])

    def test_garde_detecte_un_code_sans_consommateur(self):
        # Test-du-test : sur une arborescence sans le littéral, le code est
        # nommé ; avec une déclaration de permission qui le porte, il ne l'est plus.
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            racine = Path(d)
            (racine / 'apps' / 'x').mkdir(parents=True)
            vue = racine / 'apps' / 'x' / 'views.py'
            vue.write_text("class V:\n    pass\n", encoding='utf-8')
            self.assertFalse(consommateurs(['crm_export'], racine)['crm_export'])
            vue.write_text("class V:\n    write_permission = 'crm_export'\n",
                           encoding='utf-8')
            self.assertTrue(consommateurs(['crm_export'], racine)['crm_export'])
            # Un littéral dans un test ou le catalogue ne compte pas.
            (racine / 'apps' / 'x' / 'tests_v.py').write_text(
                "X = 'ventes_export'\n", encoding='utf-8')
            self.assertFalse(consommateurs(['ventes_export'], racine)['ventes_export'])
