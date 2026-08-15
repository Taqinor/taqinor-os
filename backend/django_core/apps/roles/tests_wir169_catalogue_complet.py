"""WIR169 — garde GÉNÉRIQUE : tout code de permission déclaré par un ViewSet
existe au catalogue ``roles.ALL_PERMISSIONS``.

Le trou BTP/assurances (4 codes gardant de vraies routes sans jamais figurer au
catalogue, donc 403 pour TOUT porteur de rôle fin, Directeur inclus) n'était
pas détectable : rien ne reliait les ``read_permission``/``write_permission``
posés dans ``apps/*/views.py`` au catalogue qui décide de leur attribution.

Ce test ferme la classe entière du défaut : il lit les sources des vues de
CHAQUE app et exige que chaque littéral déclaré soit connu du catalogue. Une
future app qui déclare ``foo_voir`` sans l'enregistrer échoue ici, pas en
production.

Analyse SYNTAXIQUE (``ast``) et non par import : aucune app n'est chargée, le
test reste rapide et ne dépend d'aucun réglage d'environnement.
"""
import ast
import pathlib

from django.test import SimpleTestCase

from apps.roles.models import ALL_PERMISSIONS

# Racine ``backend/django_core`` (ce fichier vit dans ``apps/roles/``).
RACINE = pathlib.Path(__file__).resolve().parent.parent

CHAMPS = {'read_permission', 'write_permission'}


def _fichiers_de_vues():
    """Tous les modules de vues des apps : ``views.py`` et paquets ``views/``."""
    fichiers = []
    for app in sorted(p for p in RACINE.iterdir() if p.is_dir()):
        fichiers.extend(app.glob('views.py'))
        fichiers.extend(app.glob('views_*.py'))
        fichiers.extend((app / 'views').glob('*.py'))
    return fichiers


def _constantes_chaine(arbre):
    """Constantes chaîne de premier niveau d'un module (``NOM = 'valeur'``)."""
    table = {}
    for noeud in arbre.body:
        if not isinstance(noeud, ast.Assign):
            continue
        if not (isinstance(noeud.value, ast.Constant)
                and isinstance(noeud.value.value, str)):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name):
                table[cible.id] = noeud.value.value
    return table


def _codes_declares(chemin):
    """Codes affectés à ``read_permission``/``write_permission``.

    Deux formes réelles du dépôt : le littéral direct (``'btp_voir'``) et la
    constante nommée (``DOUANE_RESPONSABLE``, définie dans le module de vues ou
    dans le ``permissions.py`` de l'app). Les deux gardent de vraies routes, les
    deux doivent donc exister au catalogue. Une valeur calculée ou ``None``
    (« aucune permission requise de ce côté ») n'a rien à vérifier.
    """
    arbre = ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
    constantes = _constantes_chaine(arbre)
    perms = chemin.parent / 'permissions.py'
    if not perms.exists():
        perms = chemin.parent.parent / 'permissions.py'
    if perms.exists():
        constantes = {
            **_constantes_chaine(
                ast.parse(perms.read_text(encoding='utf-8'),
                          filename=str(perms))),
            **constantes,
        }
    trouves = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        cibles = {c.id for c in noeud.targets if isinstance(c, ast.Name)}
        if not (cibles & CHAMPS):
            continue
        valeur = noeud.value
        if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
            trouves.add(valeur.value)
        elif isinstance(valeur, ast.Name) and valeur.id in constantes:
            trouves.add(constantes[valeur.id])
    return trouves


class CataloguePermissionsCompletTests(SimpleTestCase):
    def test_tout_code_declare_par_une_vue_existe_au_catalogue(self):
        catalogue = set(ALL_PERMISSIONS)
        manquants = {}
        for chemin in _fichiers_de_vues():
            for code in _codes_declares(chemin) - catalogue:
                manquants.setdefault(code, []).append(
                    str(chemin.relative_to(RACINE)))
        self.assertEqual(
            manquants, {},
            'Codes de permission gardant de vraies routes mais ABSENTS de '
            'roles.ALL_PERMISSIONS (tout porteur de rôle fin recevra 403, '
            'Directeur inclus) : %s' % manquants)

    def test_la_garde_voit_bien_les_codes_btp(self):
        """Sanity : le scanner trouve réellement quelque chose à vérifier."""
        codes = set()
        for chemin in _fichiers_de_vues():
            codes |= _codes_declares(chemin)
        self.assertIn('btp_voir', codes)
        self.assertIn('assurances_voir', codes)
